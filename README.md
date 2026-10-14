<p align="center"><img src="icon.png" width="128" alt="Icône VidMix"></p>

# VidMix

**Diaporama d'images et de vidéos pour Mac et Windows.**

VidMix enchaîne vos photos et vos vidéos dans une fenêtre d'affichage indépendante (idéale pour un second écran ou un projecteur), pilotée depuis une fenêtre de contrôle avec une playlist que l'on peut mélanger, trier, réordonner, enregistrer et rouvrir.

Programme en un seul fichier (`main.py`), écrit en Python avec PyQt5 et VLC. Interface en français.

---

## Fonctions

**Diaporama**
- Photos et vidéos dans la même fenêtre d'affichage, enchaînées automatiquement.
- Durée des photos réglable (1 à 300 s), option **Boucle**.
- **Fondu enchaîné** entre deux photos (de « Aucun » à 3 s).
- Plein écran (bouton, touche `F11` ou `F`, double-clic ; `Échap` pour quitter).
- Les photos de téléphone s'affichent dans le bon sens (orientation EXIF respectée).

**Playlist**
- Ajout de fichiers, d'un **dossier entier avec ses sous-dossiers**, ou par glisser-déposer.
- Les fichiers **cachés** (`.DS_Store`, `._photo.jpg`…) et ceux de **moins de 10 Ko** sont ignorés, avec un message qui indique combien.
- **Mélanger** l'ordre en un clic.
- **Trier** par nom, date de modification, date de création, date d'ajout, taille ou type (images/vidéos d'abord), dans les deux sens, plus « Inverser l'ordre ».
- **Déplacer les lignes à la souris**.
- **Enregistrer / Ouvrir une playlist** (fichier `.vidmix`) : ordre, durées, fondu, filtre, boucle et orientation de chaque fichier sont conservés.

**Vidéos**
- Barre de progression (un clic saute à l'endroit voulu), temps écoulé / durée.
- Volume et bouton **Muet**, conservés d'une vidéo à l'autre.

**Orientation fichier par fichier**
- Chaque photo ou vidéo peut avoir son propre angle (0°, 90°, 180°, 270°).
- Boutons *Tourner à gauche / à droite*, liste d'angles, *Appliquer cet angle à tous*.
- L'angle est affiché dans la playlist, par exemple `[IMG]  photo.jpg   (90°)`, et suit le fichier quand on trie, mélange ou déplace.

**Filtres (photos)** : noir et blanc, flou.

---

## Installation

### Windows : en un clic

1. Installez [VLC](https://www.videolan.org) en **version 64 bits** (nécessaire pour les vidéos) et Python 3 si ce n'est pas déjà fait.
2. Double-cliquez sur **`Installer_VidMix.bat`**.
   - Windows peut afficher « Windows a protégé votre ordinateur » : cliquez sur *Informations complémentaires*, puis *Exécuter quand même*.
3. L'installeur crée le dossier `VidMix` dans votre dossier personnel, prépare les composants, ajoute une icône **VidMix** (celle du logo ci-dessus) sur le Bureau et lance le programme.

Pour mettre à jour : relancez simplement le dernier `Installer_VidMix.bat` (l'ancien `main.py` est gardé en sauvegarde sous le nom `main_sauvegarde.py`).

### Mac

Prérequis : **Python 3** (testé avec 3.9) et **VLC** (`VLC.app` dans Applications).

Dans le Terminal :

```bash
mkdir -p ~/VidMix && cd ~/VidMix && python3 -m venv .venv
source .venv/bin/activate && pip install pyqt5 python-vlc
```

Copiez ensuite `main.py` dans le dossier `~/VidMix`, puis lancez :

```bash
cd ~/VidMix && source .venv/bin/activate && python main.py
```

**Icône à double-cliquer (sans Terminal)** : cette commande crée `VidMix.app` sur le Bureau. Déplacez-la ensuite dans **Applications**, d'où vous pourrez la glisser dans le Dock.

```bash
osacompile -o ~/Desktop/VidMix.app -e 'do shell script "~/VidMix/.venv/bin/python ~/VidMix/main.py > ~/VidMix/vidmix.log 2>&1 &"'
```

**Donner son icône à `VidMix.app`** : placez `VidMix.icns` (fourni avec le projet) dans le dossier `~/VidMix`, puis (en adaptant le chemin si vous avez rangé l'application ailleurs que dans Applications) :

```bash
cp ~/VidMix/VidMix.icns /Applications/VidMix.app/Contents/Resources/applet.icns && touch /Applications/VidMix.app
```

Si le Finder garde l'ancienne icône, quittez-le avec `killall Finder`. Autre méthode, sans Terminal : dans le Finder, sélectionnez `VidMix.app`, faites `Cmd + I`, puis glissez `icon.png` ou `VidMix.icns` sur la petite icône en haut à gauche de la fenêtre d'informations.

L'icône du Dock et des fenêtres, elle, est dessinée par le programme lui-même : rien à configurer.

> Ne supprimez ni ne déplacez le dossier `~/VidMix` : l'icône y retrouve le programme.
> Au premier lancement, macOS peut demander l'autorisation d'accéder à vos dossiers (Images, Bureau…) : choisissez **Autoriser**.

Pour mettre à jour : remplacez `~/VidMix/main.py` par la nouvelle version.

---

## Utilisation

1. **Ajoutez** des fichiers ou un dossier (boutons ou glisser-déposer).
2. Réglez au besoin la durée des photos, le fondu, l'orientation de certains fichiers…
3. Cliquez sur **Lecture** : la fenêtre d'affichage s'ouvre. Double-cliquez sur une ligne pour démarrer à partir de ce fichier.

### Raccourcis (fenêtre d'affichage)

| Touche | Action |
|---|---|
| `Espace` | Pause / reprise |
| `→` / `←` | Fichier suivant / précédent |
| `Maj` + `→` / `Maj` + `←` | Avancer / reculer de 10 s (vidéo) |
| `↑` / `↓` | Volume +5 / −5 |
| `M` | Couper / rétablir le son |
| `F11` ou `F`, double-clic | Plein écran |
| `Échap` | Quitter le plein écran |

### Fichiers `.vidmix`

Une playlist est un petit fichier texte (JSON) qui contient la liste des fichiers, leur angle et les réglages. On peut aussi en ouvrir un en le glissant sur la fenêtre. S'il existe déjà une playlist en cours, VidMix demande de **remplacer** ou d'**ajouter à la suite**.

Les chemins sont enregistrés tels quels : une playlist n'est donc **pas portable d'un ordinateur à l'autre** (les fichiers introuvables sont ignorés, avec un message).

---

## Formats pris en charge

- **Images** : jpg, jpeg, png, bmp, gif (première image seulement), webp, tif, tiff
- **Vidéos** (via VLC) : mp4, mkv, avi, mov, wmv, webm, m4v, flv, mpg, mpeg, 3gp, ts

---

## Limites connues

- Le fondu ne s'applique qu'**entre photos** ; avant ou après une vidéo, le passage est direct.
- Les filtres noir et blanc / flou ne concernent que les **photos**.
- Pour les vidéos, VLC fixe la rotation au démarrage de son lecteur : quand deux vidéos qui se suivent n'ont pas le même angle, VidMix recrée le lecteur, ce qui peut faire une courte pause. Tourner une vidéo pendant sa lecture la relance depuis le début.
- Les GIF animés n'affichent que leur première image.
- Linux n'a pas été testé.

---

## Dépannage

| Problème | Que faire |
|---|---|
| Les photos s'affichent mais pas les vidéos | VLC est absent, ou en 32 bits sous Windows : installez VLC 64 bits. |
| Mac : rien ne s'ouvre au double-clic sur l'icône | Regardez dans le Dock (la fenêtre peut s'ouvrir derrière), puis lisez `~/VidMix/vidmix.log`. |
| Windows : l'icône ne fait rien | Double-cliquez sur `Lancer_VidMix_diagnostic.bat` (dans le dossier `VidMix`) : la fenêtre noire affiche l'erreur. |
| Windows : l'installeur est bloqué | Voir la remarque SmartScreen plus haut. |
| Un dossier semble « incomplet » | Les fichiers cachés et ceux de moins de 10 Ko sont volontairement ignorés. |

---

## Pour les mainteneurs

- Tout le programme tient dans **`main.py`** (PyQt5 + python-vlc).
- **`Installer_VidMix.bat`** contient une copie de `main.py` et de `VidMix.ico`, encodées en base64 : **il doit être régénéré à chaque modification de `main.py`**, sinon l'installeur Windows installerait une ancienne version.
- L'icône est **dessinée par le code** (fonction `make_app_icon` de `main.py`). Les fichiers `icon.png`, `VidMix.icns` (Mac) et `VidMix.ico` (Windows) sont générés à partir de ce même dessin : si on le modifie, il faut les régénérer.
- L'historique des versions est dans [`CHANGELOG.md`](CHANGELOG.md).
