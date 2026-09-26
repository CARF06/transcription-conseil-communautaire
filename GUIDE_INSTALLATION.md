# Guide d'installation — Transcription du conseil avec identification des intervenants

Tout tourne **en local sur votre machine** : aucun audio n'est envoyé dans le cloud (important côté RGPD).

## 1. Prérequis (une seule fois)

### a. Python et ffmpeg

Sur Mac :
```bash
brew install python@3.12 ffmpeg
```
⚠️ Python 3.10 minimum requis (le Python 3.9 fourni avec macOS ne permet pas
d'installer un yt-dlp récent, et YouTube bloque les anciennes versions).

### b. Environnement et bibliothèques

```bash
cd "~/Claude/Projects/Rapport du Conseil Com"
python3.12 -m venv venv
source venv/bin/activate
pip install yt-dlp mlx-whisper faster-whisper pyannote.audio python-docx
```

### c. Jeton Hugging Face (gratuit, requis pour la diarisation)

1. Créez un compte sur https://huggingface.co
2. Acceptez les conditions de ces deux modèles (bouton « Agree ») :
   - https://huggingface.co/pyannote/speaker-diarization-3.1
   - https://huggingface.co/pyannote/segmentation-3.0
3. Créez un jeton « Read » : https://huggingface.co/settings/tokens
4. Dans le terminal :
```bash
export HF_TOKEN=hf_votre_jeton_ici
```

## 2. Premier test (10 minutes de la vidéo)

```bash
source venv/bin/activate
python transcription_conseil.py "https://www.youtube.com/watch?v=aylJBL95VC4" --duree 600
```

Résultat : `transcription_conseil.docx` avec les prises de parole horodatées,
étiquetées `SPEAKER_00`, `SPEAKER_01`, etc.

## 3. Mettre les vrais noms

Le premier passage crée `intervenants.txt`. Éditez-le :

```
SPEAKER_00 = M. Dupont, président
SPEAKER_01 = Mme Martin, vice-présidente
```

Puis relancez la même commande : le Word affiche les noms.
À faire une fois par séance (en écoutant 10 secondes de chaque voix).

## 4. Séance complète

```bash
python transcription_conseil.py "URL_DE_LA_VIDEO" --intervenants 12 --modele large-v3
```

- `--intervenants N` : nombre d'élus qui parlent, si connu → meilleure séparation des voix
- `--modele large-v3` : meilleure qualité de transcription (plus lent) ; `medium` par défaut
- `--moteur mlx` (défaut si installé) : transcription sur le GPU de la puce Apple ;
  `--moteur faster-whisper` : ancien moteur, sur CPU uniquement

⏱️ Mesuré le 26/09/2026 (large-v3, mlx, diarisation sur GPU) : environ **1× la
durée de la vidéo**, soit ~1 h 30 pour 1 h 30 de séance. Avant, avec faster-whisper
sur CPU, il fallait 5 h. `large-v3-turbo` est 2× plus rapide sur la transcription,
mais la ponctuation et les montants sont moins fiables.
Chaque lancement affiche un récapitulatif des temps par étape, archivé dans
`travail_transcription/<vidéo>/chronometrage.log`.
Changer de moteur n'invalide pas le cache : ajoutez `--recalculer` pour retraiter.

## Dépannage

| Problème | Solution |
|---|---|
| `401 Unauthorized` (pyannote) | Jeton HF manquant ou conditions des 2 modèles non acceptées |
| Voix mal séparées | Ajoutez `--intervenants N` ; vérifiez que l'audio YouTube est de bonne qualité |
| Trop lent | Utilisez `--modele small` pour les tests |
| `yt-dlp` : HTTP 403 Forbidden | `pip install -U yt-dlp` ; si la version reste ancienne, votre Python est < 3.10 → recréez le venv avec python3.12 |
| Document généré vide (0 seconde de transcription) | L'audio est trop faible pour le détecteur de voix de Whisper (vérifiable avec `ffmpeg -i audio.wav -af volumedetect -f null -` : `mean_volume` en dessous de -50 dB est suspect). Depuis la version du script avec normalisation `loudnorm`, relancez avec `--recalculer` pour retraiter avec le volume corrigé — le cache d'un run à 0 segment n'est sinon jamais recalculé automatiquement |
| 0 segment ou texte absurde (« Sous-titres réalisés par Amara.org ») alors que le volume est normal | Canaux stéréo en opposition de phase : ils s'annulent au passage en mono. Test : `ffmpeg -i audio.mp3 -af "pan=mono\|c0=0.5*c0+0.5*c1,volumedetect" -f null -` donne ~-66 dB contre ~-30 dB pour un canal seul. Le script le détecte désormais et n'utilise que le canal gauche (message ⚠️ au lancement) ; relancez avec `--recalculer` (cas de la séance du 25/09/2026) |

## Évolutions possibles (v2)

- **Enrôlement vocal** : banque d'empreintes des élus pour attribuer les noms automatiquement à chaque séance, sans étape manuelle
- Génération directe d'un compte rendu synthétique à partir de la transcription
