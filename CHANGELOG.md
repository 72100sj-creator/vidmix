# Journal des modifications

Toutes les évolutions notables de VidMix sont notées ici, de la plus récente à la plus ancienne.

## [4.0] - 2026-10-13

### Ajouté
- **Orientation fichier par fichier** : chaque photo ou vidéo a son propre angle (0°, 90°, 180°, 270°).
  - Nouveau cadre « Orientation du fichier sélectionné (ou en cours de lecture) » : liste d'angles, boutons *Tourner à gauche* / *Tourner à droite*, *Appliquer cet angle à tous*.
  - L'angle s'applique aux fichiers sélectionnés (sélection multiple possible), sinon au fichier en cours de lecture.
  - L'angle est affiché dans la playlist, par exemple `(90°)`.
  - L'angle est conservé quand on trie, mélange ou déplace les lignes, et il est enregistré dans les fichiers `.vidmix`.

### Modifié
- L'orientation n'est plus un réglage global.
- Les anciennes playlists (un seul angle pour tous les fichiers) restent lisibles : leur angle est appliqué à chaque fichier.
- Pour les vidéos, le lecteur VLC n'est recréé que lorsque l'angle change d'une vidéo à l'autre.
- Le programme et l'installeur Windows (`Installer_VidMix.bat`) sont mis à jour ensemble.

## [3.0] - 2026-10-12

### Ajouté
- **Barre de progression** des vidéos avec temps écoulé / durée ; un clic saute à l'endroit voulu, et on peut la faire glisser.
- **Volume** et bouton **Muet**, conservés d'une vidéo à l'autre.
- **Fondu enchaîné** entre deux photos (réglable de « Aucun » à 3 s, enregistré dans les playlists).
- Raccourcis clavier dans la fenêtre d'affichage (utiles en plein écran) : `↑` `↓` volume, `M` muet, `Maj` + `←` `→` pour reculer ou avancer de 10 s.

### Modifié
- Une photo reste entièrement visible pendant la durée choisie ; le fondu s'y ajoute.
- Affichage des photos plus net sur les écrans haute définition (Retina).

## [2.0] - 2026-10-11

### Ajouté
- **Mélanger** la playlist en un clic.
- **Trier** la playlist : nom, date de modification, date de création, date d'ajout, taille, type (images ou vidéos d'abord), dans les deux sens, plus « Inverser l'ordre actuel ».
- **Déplacer les lignes à la souris** pour changer l'ordre.
- **Enregistrer / Ouvrir une playlist** (fichiers `.vidmix`), avec le choix de remplacer ou d'ajouter à la suite ; ouverture possible par glisser-déposer.
- **Lancement en un clic** :
  - Mac : icône `VidMix.app`, sans Terminal.
  - Windows : `Installer_VidMix.bat`, un seul fichier qui installe tout et crée l'icône du Bureau.

## [1.0] - 2026-10-11

### Ajouté
- Réécriture complète en un seul fichier (`main.py`) pour Mac et Windows, en remplacement des prototypes.
- Fenêtre de contrôle (playlist en haut, boutons dessous) et fenêtre d'affichage indépendante, avec plein écran.
- Photos et vidéos enchaînées dans la même fenêtre ; lecture des vidéos par VLC.
- Ajout de fichiers, de dossiers avec leurs sous-dossiers, et par glisser-déposer.
- Les fichiers cachés et ceux de moins de 10 Ko sont ignorés.
- Durée des photos réglable, option Boucle, filtres noir et blanc / flou (photos), orientation des photos de téléphone respectée.

## [0.x] - début octobre 2026

- Prototypes initiaux, abandonnés au profit de la réécriture 1.0.
