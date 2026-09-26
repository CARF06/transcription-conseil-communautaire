#!/usr/bin/env python3
"""
Pipeline de transcription d'un conseil communautaire avec identification
des intervenants (diarisation). Tout tourne en local.

Étapes :
  1. Télécharge l'audio d'une vidéo YouTube (yt-dlp)
  2. Transcrit en français (faster-whisper)
  3. Identifie les prises de parole par locuteur (pyannote.audio)
  4. Applique les noms réels via le fichier intervenants.txt de la séance
  5. Exporte un document Word + un fichier texte

Chaque vidéo/séance a son propre dossier dans travail_transcription/,
avec son cache et son fichier intervenants.txt. Le résultat est réutilisé
tant que les paramètres (source, durée, modèle, nb d'intervenants) ne
changent pas — appliquer les noms est donc instantané.

Usage :
  python transcription_conseil.py "https://www.youtube.com/watch?v=XXXX"
  python transcription_conseil.py audio.mp3                 # fichier local
  python transcription_conseil.py URL --duree 600           # test sur 10 min
  python transcription_conseil.py URL --intervenants 12     # nb connu d'élus
  python transcription_conseil.py URL --recalculer          # ignorer le cache

Prérequis : voir GUIDE_INSTALLATION.md (jeton Hugging Face requis).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

RACINE_TRAVAIL = Path("travail_transcription")


def erreur(message: str):
    sys.exit(f"\n❌ {message}")


def identifiant_seance(source: str, duree: int | None) -> str:
    """Identifiant stable par vidéo/fichier (+ durée si extrait de test)."""
    if source.startswith("http"):
        m = re.search(r"(?:v=|youtu\.be/|/live/)([\w-]{8,})", source)
        base = m.group(1) if m else hashlib.md5(source.encode()).hexdigest()[:10]
    else:
        base = Path(source).stem
    return base + (f"_extrait{duree}s" if duree else "")


def telecharger_audio(url: str, dossier: Path) -> Path:
    fichier = dossier / "audio.mp3"
    if fichier.exists():
        print(f"⏬ Audio déjà téléchargé ({fichier}), réutilisé.")
        return fichier
    print("⏬ Téléchargement de l'audio…")
    try:
        subprocess.run(
            ["yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "0",
             "--remote-components", "ejs:github",
             "-o", str(dossier / "audio.%(ext)s"), url],
            check=True,
        )
    except FileNotFoundError:
        erreur("yt-dlp introuvable. Activez le venv (source venv/bin/activate) "
               "ou installez-le : pip install yt-dlp")
    except subprocess.CalledProcessError:
        erreur("Échec du téléchargement YouTube. Causes fréquentes :\n"
               "  - yt-dlp trop ancien (YouTube change souvent) : pip install -U yt-dlp\n"
               "  - vidéo privée/supprimée : vérifiez l'URL dans un navigateur")
    if not fichier.exists():
        erreur("L'audio n'a pas été produit par yt-dlp (format inattendu ?).")
    return fichier


def volume_moyen(source: Path, filtre: str) -> float | None:
    """Volume moyen (dB) d'un extrait de 2 min pris au milieu de l'audio."""
    duree = duree_audio(source)
    if duree is None:
        return None
    try:
        r = subprocess.run(
            ["ffmpeg", "-ss", str(max(0, duree / 2 - 60)), "-t", "120",
             "-i", str(source), "-af", f"{filtre},volumedetect", "-f", "null", "-"],
            capture_output=True, text=True)
        m = re.search(r"mean_volume: (-?[\d.]+) dB", r.stderr)
        return float(m.group(1)) if m else None
    except FileNotFoundError:
        return None


def phase_inversee(source: Path) -> bool:
    """Vrai si les canaux gauche/droit s'annulent quand on les mélange en mono.

    Certaines captations (ex. séance du 25/09/2026) ont un canal en opposition
    de phase : chaque canal seul est normal (~-30 dB) mais la somme mono tombe
    à ~-66 dB, et Whisper ne « voit » alors plus aucune parole.
    """
    gauche = volume_moyen(source, "pan=mono|c0=c0")
    somme = volume_moyen(source, "pan=mono|c0=0.5*c0+0.5*c1")
    return gauche is not None and somme is not None and gauche - somme > 15


def extraire_wav(source: Path, dossier: Path, duree: int | None) -> Path:
    if not source.exists():
        erreur(f"Fichier audio introuvable : {source}")
    wav = dossier / "audio.wav"
    cmd = ["ffmpeg", "-y", "-i", str(source)]
    if duree:
        cmd += ["-t", str(duree)]
    filtres = []
    if phase_inversee(source):
        print("⚠️ Canaux stéréo en opposition de phase détectés : seul le canal "
              "gauche est utilisé (le mixage mono annulerait la voix).")
        filtres.append("pan=mono|c0=c0")
    # Normalisation du volume : certaines captations (webcam/salle plutôt que
    # sono/pupitre) sont beaucoup trop faibles pour le VAD de Whisper, qui
    # filtre alors tout comme du silence (0 segment en sortie). loudnorm
    # ramène le niveau à une cible standard (-16 LUFS) sans dénaturer la voix.
    filtres.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    cmd += ["-af", ",".join(filtres)]
    cmd += ["-ar", "16000", "-ac", "1", str(wav)]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except FileNotFoundError:
        erreur("ffmpeg introuvable : brew install ffmpeg")
    except subprocess.CalledProcessError as e:
        erreur(f"ffmpeg n'a pas pu convertir l'audio :\n{e.stderr.decode()[-500:]}")
    return wav


# Modèles Whisper convertis pour MLX (puce Apple Silicon), par nom court
MODELES_MLX = {
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "large-v3-turbo": "mlx-community/whisper-large-v3-turbo",
}


def mlx_disponible() -> bool:
    try:
        import mlx_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def transcrire(wav: Path, modele: str, moteur: str):
    if moteur == "mlx":
        return transcrire_mlx(wav, modele)
    return transcrire_faster_whisper(wav, modele)


def transcrire_mlx(wav: Path, modele: str):
    import mlx_whisper

    depot = MODELES_MLX.get(modele, modele)
    print(f"📝 Transcription en cours (mlx-whisper, {depot} — téléchargé au "
          "1er lancement)…")
    # mlx-whisper n'a pas de filtre VAD : on s'appuie sur les garde-fous de
    # Whisper contre les hallucinations dans les silences (pauses de séance).
    # condition_on_previous_text=False évite qu'une phrase hallucinée se
    # répète en boucle sur les segments suivants.
    resultat = mlx_whisper.transcribe(
        str(wav), path_or_hf_repo=depot, language="fr",
        condition_on_previous_text=False,
        word_timestamps=True, hallucination_silence_threshold=2.0,
    )
    return [
        {"debut": s["start"], "fin": s["end"], "texte": s["text"].strip()}
        for s in resultat["segments"] if s["text"].strip()
    ]


def transcrire_faster_whisper(wav: Path, modele: str):
    from faster_whisper import WhisperModel

    print(f"📝 Chargement du modèle {modele} (téléchargement au 1er lancement — "
          f"si bloqué : hf download Systran/faster-whisper-{modele})")
    model = WhisperModel(modele, device="auto", compute_type="auto")
    print("📝 Transcription en cours…")
    # Seuil VAD abaissé (0.2 au lieu de 0.5 par défaut) : un enregistrement
    # capté par un micro d'ambiance/webcam plutôt qu'une sono peut être assez
    # faible pour que le détecteur de voix par défaut rejette TOUT comme non-
    # parole (0 segment en sortie), même quand la parole est bien audible à
    # l'oreille.
    segments, _ = model.transcribe(
        str(wav), language="fr", vad_filter=True,
        vad_parameters=dict(threshold=0.2),
    )
    resultats = [
        {"debut": s.start, "fin": s.end, "texte": s.text.strip()}
        for s in segments
    ]
    if not resultats:
        print("⚠️ Toujours 0 segment avec le VAD assoupli — nouvel essai sans VAD du "
              "tout (plus lent, peut inclure un peu de bruit dans les silences).")
        segments, _ = model.transcribe(str(wav), language="fr", vad_filter=False)
        resultats = [
            {"debut": s.start, "fin": s.end, "texte": s.text.strip()}
            for s in segments
        ]
    return resultats


def diariser(wav: Path, hf_token: str, nb_intervenants: int | None):
    from pyannote.audio import Pipeline

    print("🎙️ Identification des intervenants…")
    try:
        try:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1", token=hf_token)
        except TypeError:  # pyannote.audio < 4
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1", use_auth_token=hf_token)
    except Exception as e:
        if "403" in str(e) or "gated" in str(e).lower() or "401" in str(e):
            erreur("Accès refusé au modèle pyannote. Vérifiez (même compte que le jeton) :\n"
                   "  1. Conditions acceptées sur hf.co/pyannote/speaker-diarization-3.1\n"
                   "  2. Conditions acceptées sur hf.co/pyannote/segmentation-3.0\n"
                   "  3. Jeton de type « Read » : hf.co/settings/tokens")
        raise
    import torch
    if torch.backends.mps.is_available():
        # Processeur graphique de la puce Apple : bien plus rapide que le CPU
        pipeline.to(torch.device("mps"))
    kwargs = {"num_speakers": nb_intervenants} if nb_intervenants else {}
    try:
        resultat = pipeline(str(wav), **kwargs)
    except RuntimeError as e:
        if "mps" not in str(e).lower():
            raise
        print(f"⚠️ Échec sur le GPU Apple ({e}) — nouvel essai sur le CPU.")
        pipeline.to(torch.device("cpu"))
        resultat = pipeline(str(wav), **kwargs)
    # pyannote >= 4 enveloppe le résultat ; les versions 3.x le renvoient direct
    annotation = getattr(resultat, "speaker_diarization", resultat)
    return [
        {"debut": turn.start, "fin": turn.end, "locuteur": speaker}
        for turn, _, speaker in annotation.itertracks(yield_label=True)
    ]


def associer(segments, tours):
    """Attribue à chaque segment transcrit le locuteur au recouvrement maximal."""
    for seg in segments:
        meilleur, recouvrement = "Intervenant ?", 0.0
        for t in tours:
            r = min(seg["fin"], t["fin"]) - max(seg["debut"], t["debut"])
            if r > recouvrement:
                recouvrement, meilleur = r, t["locuteur"]
        seg["locuteur"] = meilleur
    return segments


def charger_noms(chemin: Path) -> dict:
    noms = {}
    if chemin.exists():
        for ligne in chemin.read_text(encoding="utf-8").splitlines():
            if "=" in ligne and not ligne.strip().startswith("#"):
                cle, nom = ligne.split("=", 1)
                noms[cle.strip()] = nom.strip()
    return noms


def hms(s: float) -> str:
    s = int(s)
    return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"


class Chrono:
    """Mesure la durée de chaque étape et affiche un récapitulatif."""

    def __init__(self):
        self.etapes = []
        self.debut_total = time.monotonic()

    def mesurer(self, nom: str, fonction, *args):
        debut = time.monotonic()
        resultat = fonction(*args)
        duree = time.monotonic() - debut
        self.etapes.append((nom, duree))
        print(f"⏱️ {nom} : {hms(duree)}")
        return resultat

    def recapitulatif(self, duree_audio: float | None) -> str:
        total = time.monotonic() - self.debut_total
        lignes = ["", "⏱️ Récapitulatif des temps de traitement :"]
        lignes += [f"   {nom:<28} {hms(d)}" for nom, d in self.etapes]
        lignes.append(f"   {'TOTAL':<28} {hms(total)}")
        if duree_audio:
            lignes.append(f"   (pour {hms(duree_audio)} d'audio, soit "
                          f"{total / duree_audio:.2f}× la durée réelle)")
        return "\n".join(lignes)


def duree_audio(wav: Path) -> float | None:
    try:
        return float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(wav)],
            capture_output=True, text=True, check=True).stdout.strip())
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return None


def exporter_word(segments, noms, sortie: Path, titre: str):
    from docx import Document
    from docx.shared import Pt, RGBColor

    doc = Document()
    doc.add_heading(titre, level=0)
    doc.add_paragraph("Transcription automatique — à relire avant diffusion.")

    locuteur_courant = None
    for seg in segments:
        nom = noms.get(seg["locuteur"], seg["locuteur"])
        if nom != locuteur_courant:
            p = doc.add_paragraph()
            run = p.add_run(f"\n{nom}  [{hms(seg['debut'])}]")
            run.bold = True
            run.font.size = Pt(11)
            run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
            locuteur_courant = nom
        doc.add_paragraph(seg["texte"])
    doc.save(sortie)


def exporter_texte(segments, noms, sortie: Path, titre: str):
    lignes = [titre, "Transcription automatique — à relire avant diffusion.", ""]
    locuteur_courant = None
    for seg in segments:
        nom = noms.get(seg["locuteur"], seg["locuteur"])
        if nom != locuteur_courant:
            lignes += ["", f"{nom}  [{hms(seg['debut'])}]"]
            locuteur_courant = nom
        lignes.append(seg["texte"])
    sortie.write_text("\n".join(lignes), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Transcription + diarisation d'un conseil")
    ap.add_argument("source", help="URL YouTube ou fichier audio local")
    ap.add_argument("--duree", type=int, default=None,
                    help="Limiter aux N premières secondes (test)")
    ap.add_argument("--intervenants", type=int, default=None,
                    help="Nombre d'intervenants si connu (améliore la précision)")
    ap.add_argument("--modele", default="medium",
                    help="Modèle Whisper : small | medium | large-v3 | large-v3-turbo")
    ap.add_argument("--moteur", choices=["mlx", "faster-whisper"], default=None,
                    help="Moteur de transcription. Défaut : mlx (GPU de la puce "
                         "Apple) s'il est installé, sinon faster-whisper (CPU)")
    ap.add_argument("--nom", default=None,
                    help="Nom lisible de la séance, utilisé comme dossier de "
                         "sortie (ex: \"Conseil 2026-06-17\"). "
                         "Défaut : identifiant de la vidéo.")
    ap.add_argument("--recalculer", action="store_true",
                    help="Ignorer le cache et retraiter l'audio")
    args = ap.parse_args()

    # Dossier technique (cache, audio) : lié à la vidéo, jamais renommé
    seance = identifiant_seance(args.source, args.duree)
    dossier = RACINE_TRAVAIL / seance
    dossier.mkdir(parents=True, exist_ok=True)

    # Dossier de sortie : un par conseil, au nom lisible
    dossier_sortie = Path(args.nom) if args.nom else Path(f"Conseil_{seance}")
    dossier_sortie.mkdir(parents=True, exist_ok=True)

    parametres = {"source": args.source, "duree": args.duree,
                  "modele": args.modele, "intervenants": args.intervenants}
    cache = dossier / "segments.json"

    segments = None
    if cache.exists() and not args.recalculer:
        contenu = json.loads(cache.read_text(encoding="utf-8"))
        if contenu.get("parametres") == parametres:
            print(f"⚡ Résultat précédent réutilisé ({cache}).\n"
                  "   Pour retraiter l'audio : --recalculer")
            segments = contenu["segments"]
        else:
            print("ℹ️ Les paramètres ont changé depuis le dernier calcul → retraitement.")

    if segments is None:
        hf_token = os.environ.get("HF_TOKEN")
        if not hf_token:
            # Jeton enregistré une fois pour toutes par « hf auth login »
            from huggingface_hub import get_token
            hf_token = get_token()
        fichier_jeton = Path(__file__).with_name("hf_token.txt")
        if not hf_token and fichier_jeton.exists():
            # Copie du jeton dans le dossier projet (OneDrive), pour un autre Mac
            hf_token = fichier_jeton.read_text(encoding="utf-8").strip()
        if not hf_token:
            erreur("Jeton Hugging Face manquant : lancez une fois « hf auth login » "
                   "(ou export HF_TOKEN=hf_xxx) — voir GUIDE_INSTALLATION.md")

        moteur = args.moteur or ("mlx" if mlx_disponible() else "faster-whisper")
        chrono = Chrono()
        if args.source.startswith("http"):
            audio = chrono.mesurer("Téléchargement", telecharger_audio,
                                   args.source, dossier)
        else:
            audio = Path(args.source)

        wav = chrono.mesurer("Préparation de l'audio", extraire_wav,
                             audio, dossier, args.duree)
        segments = chrono.mesurer(f"Transcription ({moteur})", transcrire,
                                  wav, args.modele, moteur)
        tours = chrono.mesurer("Identification des voix", diariser,
                               wav, hf_token, args.intervenants)
        segments = associer(segments, tours)
        recap = chrono.recapitulatif(duree_audio(wav))
        print(recap)
        cache.write_text(
            json.dumps({"parametres": parametres, "segments": segments},
                       ensure_ascii=False, indent=1),
            encoding="utf-8")
        # Historique des temps, pour comparer les réglages d'une séance à l'autre
        with open(dossier / "chronometrage.log", "a", encoding="utf-8") as f:
            f.write(f"\n=== {datetime.now():%d/%m/%Y %H:%M} — modèle {args.modele}, "
                    f"moteur {moteur}, intervenants {args.intervenants}{recap}\n")

    # Fichier de correspondance des noms, dans le dossier du conseil
    fichier_noms = dossier_sortie / "intervenants.txt"
    if not fichier_noms.exists():
        ancien = dossier / "intervenants.txt"  # versions précédentes du script
        if ancien.exists():
            fichier_noms.write_text(ancien.read_text(encoding="utf-8"),
                                    encoding="utf-8")
        else:
            vus = sorted({s["locuteur"] for s in segments})
            fichier_noms.write_text(
                "# Remplacez par les vrais noms puis relancez le script :\n"
                + "\n".join(f"{v} = {v}" for v in vus), encoding="utf-8")
            print(f"ℹ️ Fichier {fichier_noms} créé : renseignez les noms des "
                  "élus puis relancez (instantané) pour les appliquer.")

    noms = charger_noms(fichier_noms)
    titre = f"{dossier_sortie.name} — Transcription " \
            f"(générée le {datetime.now():%d/%m/%Y})"
    sortie_docx = dossier_sortie / "transcription.docx"
    sortie_txt = dossier_sortie / "transcription.txt"
    exporter_word(segments, noms, sortie_docx, titre)
    exporter_texte(segments, noms, sortie_txt, titre)
    print(f"✅ Documents générés : {sortie_docx} et {sortie_txt}")


if __name__ == "__main__":
    main()
