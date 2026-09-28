# Rapport du Conseil Com — notes pour une future session (Claude Code ou autre)

## Fonctionnement du projet
Pipeline de transcription + diarisation des conseils communautaires de la CARF
(Communauté d'Agglomération de la Riviera Française), voir `GUIDE_INSTALLATION.md`
pour le détail. Commande type :

```bash
cd ~/Claude/Projects/"Rapport du Conseil Com"
source venv/bin/activate
export HF_TOKEN=hf_xxx   # jeton personnel, à exporter à chaque session shell
python transcription_conseil.py "URL_YOUTUBE" --intervenants 12 --modele large-v3 --nom "Conseil JJ-MM-AAAA"
```

## Quand Alex donne juste une URL YouTube : tout faire de bout en bout
1. Date de la séance : `yt-dlp --print "%(title)s | %(upload_date)s" URL`, puis
   confirmer avec l'appel nominal du début. Dossier `Conseil JJ-MM-AAAA`.
2. Lancer en arrière-plan (environ 1× la durée de la vidéo avec mlx) :
   `python transcription_conseil.py URL --intervenants 12 --modele large-v3 --nom "Conseil JJ-MM-AAAA"`.
   Le jeton HF est lu automatiquement : variable HF_TOKEN, sinon `hf auth login`
   (~/.cache/huggingface/token), sinon `hf_token.txt` dans le dossier projet.
   Ne jamais le demander ni le recopier dans ce fichier.
3. Vérifier le résultat : nombre de segments différent de 0, texte cohérent
   (pas de « Sous-titres réalisés par Amara.org »), récapitulatif des temps.
4. Nommer les locuteurs dans `intervenants.txt` d'après le contenu (la
   présidente annonce qui présente chaque délibération, « Merci X »…) et la
   liste des élus ci-dessous. Signaler les locuteurs fusionnés ou inconnus,
   puis relancer le script (instantané) pour appliquer les noms.
5. Mettre à jour la section « Reste à faire » et donner le temps de traitement.

## ⚠️ Doit tourner en natif sur le Mac (Terminal / Claude Code), pas via le pont Cowork
Le `venv` contient des bibliothèques compilées pour macOS/Apple Silicon (torch,
pyannote.audio...). Le pont "device bridge" utilisé par une session Cowork
cloud exécute les commandes dans une VM Linux isolée, incompatible avec ces
binaires (`python -V` y retombe sur le Python système, `yt-dlp` n'est pas
trouvé). Résultat : ce script ne peut être lancé que depuis un vrai Terminal
macOS ou une session Claude Code locale — pas via l'exécution à distance
d'une session Cowork cloud.

## Convention de nommage
Date **toujours au format français JJ-MM-AAAA** (demande d'Alex). Un dossier
par séance : `Conseil JJ-MM-AAAA` (date de la séance, pas de la vidéo). Les
fichiers s'appellent `Transcription du conseil communautaire du JJ-MM-AAAA.docx`
(et `.txt`). Le script convertit tout seul un `--nom` donné en AAAA-MM-JJ. Voir `Conseil 06-2026 test/` (extrait de test) et
`Conseil 30-07-2026/` (séance complète) comme exemples.

## Élus déjà identifiés (à réutiliser, pas à re-découvrir)
⚠️ Les étiquettes `SPEAKER_00`, `SPEAKER_01`... ne sont **pas stables** d'une
séance à l'autre (recalculées à chaque diarisation). Cette liste sert de
référence de noms/fonctions pour accélérer l'identification à l'oreille —
elle ne se substitue pas au ré-écoute de chaque séance.

Liste complète des 48 élus (source officielle :
https://www.riviera-francaise.fr/elus/, vérifiée le 25/09/2026, sections
« Bureau communautaire » et « Les conseillers communautaires ») :

Présidente et 15 vice-présidents :

| Nom | Commune | Fonction |
|---|---|---|
| Alexandra MASSON | Menton | Présidente |
| Gérard SPINELLI | Beausoleil | VP — Attractivité économique, patrimoine culturel et tourisme |
| Albert FILIPPI | Sainte-Agnès | VP — Rapports transfrontaliers |
| Patrick CESARI | Roquebrune-Cap-Martin | VP — Aménagement de l'espace, habitat et SCoT |
| Sébastien OLHARAN | Breil-sur-Roya | VP — GEMAPI, prévention des risques et sécurité civile |
| Christophe BRUNENGO | Sospel | VP — Eau et assainissement |
| Valentin LOPEZ | La Turbie | VP — Environnement et cadre de vie |
| Fabrice PASTOR | Gorbio | VP — Déchets et collectes |
| Sylvie CALVIN-MOREAU | Tende | VP — Pôle Santé |
| Anne-Marie ARSENTO-CURTI | Castellar | VP — Agriculture |
| José PASTORELLI | La Brigue | VP — Grands travaux |
| Olivier CHANTREAU | Castillon | VP — Transport et audiovisuel |
| Philippe OUDOT | Fontan | VP — Communication, protocole, événementiel et RH |
| Guy BONVALLET | Moulinet | VP — Politique de la Ville |
| David BROUSTE | Saorge | VP — Finances |
| Jean-Christophe STORAÏ | Menton | VP — Administration Générale |

32 conseillers communautaires (pas de délégation individuelle indiquée sur le
site) :

Catherine ALSTADT (Menton), Elena AVRAMOVIC (Beausoleil), Fadile BOUFIASSA
(Beausoleil), Claude CALVIN (Menton), Florence CASARO-MAZZA
(Roquebrune-Cap-Martin), Florent CHAMPION (Menton), Guillaume CONTESSE
(Roquebrune-Cap-Martin), Sabrina DERIU (La Turbie), Gérard DESTEFANIS
(Beausoleil), Sophie ECKENBERG (Menton), Martine ELICRISIO (Menton), Isabelle
FAYAT (Menton), Ida FERRARI (Menton), Martine FERRERO (Sospel), Cindy
GENOVESE (Beausoleil), Jean-Mario LORENZI (Sospel), Patricia LORENZI
(Roquebrune-Cap-Martin), David MARCHISIO (Menton), Richard MARCON
(Beausoleil), Auréline MARI (Roquebrune-Cap-Martin), Antoine MASCARELLO
(Tende), Daniel MINEO (Menton), Richard MIQUELIS (Menton), Michel MOURADIAN
(Roquebrune-Cap-Martin), Dominique NICOLAÏ (Roquebrune-Cap-Martin), Kathleen
WAEYTENS (Menton), Nicolas LITTARDI (Menton), **Louis SARKOZY (Menton)**,
Isabelle SAUVE (Breil-sur-Roya), Virginie SIMONCINI (Menton), Nicolas
SPINELLI (Beausoleil), Pascale VERAN (Menton).

⚠️ Deux Spinelli distincts : Gérard SPINELLI (VP, Beausoleil) et Nicolas
SPINELLI (conseiller, Beausoleil) — ne pas les confondre.

Louis SARKOZY est bien un élu réel (conseiller communautaire, Menton) :
confirmé sur la page officielle ci-dessus. Ce tableau devrait maintenant être
complet sur les 48 ; si un nom entendu en séance n'y figure toujours pas,
vérifier d'abord une variante orthographique avant de le supposer erroné.

Florent CHAMPION a été secrétaire de séance lors des deux dernières séances
(rôle qui peut tourner d'une séance à l'autre — à confirmer à chaque fois).

### Reste à faire
Séance du 25 septembre 2026 (`Conseil 25-09-2026/`, vidéo O4W3nYsIDZg) :
audio stéréo en opposition de phase (le script ne garde plus que le canal
gauche dans ce cas). 10 locuteurs sur 12 ont été nommés d'après le contenu.
Reste : SPEAKER_02 regroupe plusieurs voix (D. Brouste, G. Spinelli,
J. Pastorelli, services) et devra être découpé à l'oreille. SPEAKER_05 est
inconnu et SPEAKER_00 (OUDOT, RH) est à confirmer.

Sur la séance du 30 juillet, 8 locuteurs sur 11 (SPEAKER_00, 01, 02, 05 à 09)
restent encore à nommer dans `Conseil 30-07-2026/intervenants.txt`.

Appel nominal reconstitué (début de cette séance, noms corrigés d'après la
liste officielle ci-dessus — indique qui était présent/excusé, pas quel
`SPEAKER_XX` leur correspond, ça reste à faire à l'oreille) :
Alexandra MASSON (présidente), Gérard SPINELLI (excusé, pouvoir à Gérard
DESTEFANIS), Albert FILIPPI (excusé, pouvoir à Patrick CESARI), Patrick
CESARI, Sébastien OLHARAN, Christophe BRUNENGO, Valentin LOPEZ (excusé),
Fabrice PASTOR, Sylvie CALVIN-MOREAU, Anne-Marie ARSENTO-CURTI (retard,
pouvoir à Fabrice PASTOR en attendant), José PASTORELLI, Olivier CHANTREAU,
Philippe OUDOT (excusé, pouvoir à José PASTORELLI), Guy BONVALLET, David
BROUSTE (excusé), Jean-Christophe STORAÏ, Catherine ALSTADT (excusée,
pouvoir à Nicolas LITTARDI), Elena AVRAMOVIC (pouvoir à Richard MARCON),
Fadile BOUFIASSA (excusée), Claude CALVIN, Florence CASARO-MAZZA, Guillaume
CONTESSE, Sabrina DERIU (excusée), Gérard DESTEFANIS (présent, porte le
pouvoir de G. Spinelli), Sophie ECKENBERG (excusée, pouvoir à Daniel MINEO).
(Liste incomplète : la transcription continue au-delà de ce point.)

## Évolutions possibles (v2)
- Enrôlement vocal : banque d'empreintes des élus pour attribuer les noms
  automatiquement, sans étape manuelle.
- Génération directe d'un compte rendu synthétique à partir de la
  transcription (au-delà du verbatim horodaté).
