# Transcription des conseils communautaires — CARF

Transcription automatique et identification des intervenants (diarisation) des
séances du conseil communautaire de la Communauté d'Agglomération de la
Riviera Française, à partir de la vidéo YouTube de la séance.

Tout tourne en local sur un Mac Apple Silicon : aucun audio n'est envoyé dans
le cloud. Les outils utilisés sont yt-dlp, mlx-whisper (ou faster-whisper) et
pyannote.audio. Le résultat est un document Word et un fichier texte
horodatés, avec les noms des élus.

```bash
pip install -r requirements.txt
python transcription_conseil.py "URL_YOUTUBE" --intervenants 12 --modele large-v3 --nom "Conseil AAAA-MM-JJ"
```

- Installation, jeton Hugging Face et dépannage : [GUIDE_INSTALLATION.md](GUIDE_INSTALLATION.md)
- Notes de travail et liste des élus : [AGENTS.md](AGENTS.md)
