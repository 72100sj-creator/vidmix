#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
VidMix - diaporama d'images et de videos (version propre, fichier unique).

- Fenetre "Controles" : playlist en haut, boutons en dessous.
- Fenetre "Viewer" independante : affiche les images et les videos a la suite.
- Les fichiers caches et les fichiers de moins de 10 Ko sont ignores.
"""
import json
import os
import random
import re
import sys

from PyQt5 import QtWidgets, QtGui, QtCore

try:
    import vlc
except Exception as exc:  # VLC ou python-vlc absent
    vlc = None
    VLC_ERROR = str(exc)
else:
    VLC_ERROR = ""

MIN_SIZE = 10 * 1024  # 10 Ko : en dessous, le fichier est ignore
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".m4v", ".flv",
             ".mpg", ".mpeg", ".3gp", ".ts"}


# ----------------------------------------------------------------------
# Outils fichiers
# ----------------------------------------------------------------------
def media_kind(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXT:
        return "image"
    if ext in VIDEO_EXT:
        return "video"
    return None


def is_hidden(path):
    """Vrai si le fichier/dossier est cache (nom en '.' ou attribut Windows)."""
    name = os.path.basename(os.path.normpath(path))
    if name.startswith("."):
        return True
    if os.name == "nt":
        try:
            import ctypes
            attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
            if attrs != -1 and (attrs & 0x2 or attrs & 0x4):  # cache ou systeme
                return True
        except Exception:
            pass
    return False


def natural_key(text):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r"(\d+)", text)]


def modified_time(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def creation_time(path):
    """Date de création (Mac/Windows) ; à défaut, la meilleure date disponible."""
    try:
        st = os.stat(path)
        return getattr(st, "st_birthtime", st.st_ctime)
    except OSError:
        return 0


def file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def fmt_time(ms):
    """Millisecondes -> '1:05' ou '1:02:03'."""
    try:
        total = max(0, int(ms // 1000))
    except (TypeError, ValueError):
        total = 0
    h, rest = divmod(total, 3600)
    m, sec = divmod(rest, 60)
    return "%d:%02d:%02d" % (h, m, sec) if h else "%d:%02d" % (m, sec)


def check_file(path):
    """Retourne 'ok', 'ignore' (cache / trop petit) ou 'autre' (pas un media)."""
    if media_kind(path) is None:
        return "autre"
    try:
        if is_hidden(path) or os.path.getsize(path) < MIN_SIZE:
            return "ignore"
    except OSError:
        return "ignore"
    return "ok"


def collect_folder(folder):
    """Parcourt un dossier et ses sous-dossiers. Retourne (fichiers, nb_ignores)."""
    found, ignored = [], 0
    for root, dirs, files in os.walk(folder):
        dirs[:] = sorted((d for d in dirs if not is_hidden(os.path.join(root, d))),
                         key=natural_key)
        for name in sorted(files, key=natural_key):
            path = os.path.join(root, name)
            result = check_file(path)
            if result == "ok":
                found.append(path)
            elif result == "ignore":
                ignored += 1
    return found, ignored


# ----------------------------------------------------------------------
# Fenetre d'affichage (viewer)
# ----------------------------------------------------------------------
class PlaylistList(QtWidgets.QListWidget):
    """Liste : on peut y déplacer les lignes à la souris, et y déposer des fichiers."""
    reordered = QtCore.pyqtSignal()
    paths_dropped = QtCore.pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.InternalMove)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
            event.acceptProposedAction()
            self.paths_dropped.emit(paths)
        else:
            super().dropEvent(event)
            self.reordered.emit()


class ClickSlider(QtWidgets.QSlider):
    """Curseur horizontal : un clic saute directement à l'endroit cliqué."""

    def __init__(self):
        super().__init__(QtCore.Qt.Horizontal)
        self._dragging = False
        self.setFocusPolicy(QtCore.Qt.NoFocus)

    def _value_at(self, x):
        return QtWidgets.QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), int(x), max(1, self.width()))

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.isEnabled():
            self._dragging = True
            self.setValue(self._value_at(event.pos().x()))
            self.sliderPressed.emit()
            self.sliderMoved.emit(self.value())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self.setValue(self._value_at(event.pos().x()))
            self.sliderMoved.emit(self.value())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging and event.button() == QtCore.Qt.LeftButton:
            self._dragging = False
            self.sliderReleased.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class ImageView(QtWidgets.QWidget):
    """Affiche une image centrée (proportions gardées), avec fondu enchaîné possible."""

    def __init__(self):
        super().__init__()
        self._src = None     # image d'origine
        self._cur = None     # image adaptée à la taille de la fenêtre
        self._old = None     # image précédente (visible seulement pendant un fondu)
        self._text = ""
        self._fade = 1.0     # 0 = ancienne image seule, 1 = nouvelle image seule
        self.setSizePolicy(QtWidgets.QSizePolicy.Ignored, QtWidgets.QSizePolicy.Ignored)
        self._anim = QtCore.QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QtCore.QEasingCurve.InOutQuad)
        self._anim.valueChanged.connect(self._on_fade)
        self._anim.finished.connect(self._on_fade_done)

    # --- utilitaires ---------------------------------------------------
    def _scaled(self, pix):
        if pix is None or pix.isNull():
            return None
        dpr = self.devicePixelRatioF()
        size = QtCore.QSize(int(self.width() * dpr), int(self.height() * dpr))
        if size.width() < 2 or size.height() < 2:
            return None
        out = pix.scaled(size, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        out.setDevicePixelRatio(dpr)
        return out

    def _on_fade(self, value):
        self._fade = float(value)
        self.update()

    def _on_fade_done(self):
        self._old = None
        self._fade = 1.0
        self.update()

    # --- API -----------------------------------------------------------
    def show_image(self, pixmap, fade_ms=0):
        self._anim.stop()
        self._text = ""
        if pixmap is None or pixmap.isNull():
            self.clear_all()
            return
        previous = self._cur
        self._src = pixmap
        self._cur = self._scaled(pixmap)
        if fade_ms > 0:
            self._old = previous        # None => fondu depuis le noir
            self._fade = 0.0
            self._anim.setDuration(int(fade_ms))
            self._anim.start()
        else:
            self._old = None
            self._fade = 1.0
        self.update()

    def show_text(self, text):
        self.clear_all()
        self._text = text
        self.update()

    def clear_all(self):
        self._anim.stop()
        self._src = self._cur = self._old = None
        self._text = ""
        self._fade = 1.0
        self.update()

    # --- dessin --------------------------------------------------------
    def _paint_pix(self, painter, pix, opacity):
        dpr = pix.devicePixelRatio() or 1.0
        x = int((self.width() - pix.width() / dpr) / 2)
        y = int((self.height() - pix.height() / dpr) / 2)
        painter.setOpacity(opacity)
        painter.drawPixmap(x, y, pix)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), QtCore.Qt.black)
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
        if self._text:
            p.setPen(QtGui.QColor("white"))
            p.drawText(self.rect(), QtCore.Qt.AlignCenter, self._text)
            return
        if self._old is not None:
            self._paint_pix(p, self._old, 1.0)
        if self._cur is not None:
            self._paint_pix(p, self._cur, self._fade)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._anim.stop()
        self._old = None
        self._fade = 1.0
        self._cur = self._scaled(self._src)


class Viewer(QtWidgets.QWidget):
    closed = QtCore.pyqtSignal()
    next_requested = QtCore.pyqtSignal()
    prev_requested = QtCore.pyqtSignal()
    pause_requested = QtCore.pyqtSignal()
    volume_step = QtCore.pyqtSignal(int)    # +5 / -5
    mute_requested = QtCore.pyqtSignal()
    seek_requested = QtCore.pyqtSignal(int)  # décalage en millisecondes

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VidMix - Viewer")
        self.resize(960, 600)
        self.setStyleSheet("background:black;")
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.stack)

        self.video_frame = QtWidgets.QFrame()
        self.video_frame.setStyleSheet("background:black;")
        self.image_view = ImageView()
        self.stack.addWidget(self.video_frame)  # index 0 : video
        self.stack.addWidget(self.image_view)   # index 1 : image

    # --- affichage -----------------------------------------------------
    def show_video_surface(self):
        self.image_view.clear_all()   # évite de revoir une ancienne photo au retour
        self.stack.setCurrentIndex(0)

    def show_pixmap(self, pixmap, fade_ms=0):
        self.stack.setCurrentIndex(1)
        self.image_view.show_image(pixmap, fade_ms)

    def show_message(self, text):
        self.stack.setCurrentIndex(1)
        self.image_view.show_text(text)

    def clear(self):
        self.stack.setCurrentIndex(1)
        self.image_view.clear_all()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # --- evenements ----------------------------------------------------
    def keyPressEvent(self, event):
        key = event.key()
        if key == QtCore.Qt.Key_Escape and self.isFullScreen():
            self.showNormal()
        elif key in (QtCore.Qt.Key_F11, QtCore.Qt.Key_F):
            self.toggle_fullscreen()
        elif key == QtCore.Qt.Key_Space:
            self.pause_requested.emit()
        elif key == QtCore.Qt.Key_Right:
            if event.modifiers() & QtCore.Qt.ShiftModifier:
                self.seek_requested.emit(10000)
            else:
                self.next_requested.emit()
        elif key == QtCore.Qt.Key_Left:
            if event.modifiers() & QtCore.Qt.ShiftModifier:
                self.seek_requested.emit(-10000)
            else:
                self.prev_requested.emit()
        elif key == QtCore.Qt.Key_Up:
            self.volume_step.emit(5)
        elif key == QtCore.Qt.Key_Down:
            self.volume_step.emit(-5)
        elif key == QtCore.Qt.Key_M:
            self.mute_requested.emit()
        else:
            super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.toggle_fullscreen()

    def closeEvent(self, event):
        self.closed.emit()
        event.accept()


# ----------------------------------------------------------------------
# Fenetre principale (controles + playlist)
# ----------------------------------------------------------------------
class VidMixWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VidMix - Contrôles")
        self.resize(640, 900)
        self.setAcceptDrops(True)

        self.items = []
        self.added = {}             # chemin -> numéro d'ordre d'ajout
        self._add_counter = 0
        self.index = -1
        self.state = "stopped"      # stopped / playing / paused
        self.rotations = {}         # chemin -> 90 / 180 / 270 (absent = 0°), propre à chaque fichier
        self.filter_name = "none"   # none / gray / blur
        self._fail_streak = 0
        self.volume = 100           # 0 à 100
        self.muted = False
        self._seeking = False       # vrai pendant qu'on déplace le curseur de la vidéo
        self._video_length = 0      # durée de la vidéo en cours (ms)
        self._audio_pending = True  # volume à (re)appliquer dès que VLC lit
        self._player_rotation = 0   # angle avec lequel le lecteur VLC actuel a été créé
        self.vlc_instance = None
        self.vlc_player = None

        self.viewer = Viewer()
        self.viewer.closed.connect(self._on_viewer_closed)
        self.viewer.next_requested.connect(self.next_item)
        self.viewer.prev_requested.connect(self.prev_item)
        self.viewer.pause_requested.connect(self.toggle_play)
        self.viewer.volume_step.connect(self._step_volume)
        self.viewer.mute_requested.connect(self._toggle_mute)
        self.viewer.seek_requested.connect(self._seek_relative)

        self.image_timer = QtCore.QTimer(self)
        self.image_timer.setSingleShot(True)
        self.image_timer.timeout.connect(self.next_item)

        self.poll_timer = QtCore.QTimer(self)
        self.poll_timer.setInterval(300)
        self.poll_timer.timeout.connect(self._poll_video)

        self._build_ui()

    # --- interface -----------------------------------------------------
    def _button(self, text, slot):
        btn = QtWidgets.QPushButton(text)
        btn.clicked.connect(lambda checked=False: slot())
        return btn

    def _row(self, widgets):
        row = QtWidgets.QHBoxLayout()
        for w in widgets:
            row.addWidget(w)
        return row

    def _build_ui(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        # 1) Playlist EN HAUT
        layout.addWidget(QtWidgets.QLabel(
            "Playlist - glissez des fichiers/dossiers pour en ajouter, "
            "glissez les lignes pour changer l'ordre :"))
        self.list = PlaylistList()
        self.list.itemDoubleClicked.connect(lambda item: self.play_index(self.list.row(item)))
        self.list.reordered.connect(self._on_list_reordered)
        self.list.paths_dropped.connect(self.handle_paths)
        layout.addWidget(self.list, stretch=1)

        # 2) Gestion de la playlist
        layout.addLayout(self._row([
            self._button("Ajouter fichiers", self.add_files),
            self._button("Ajouter dossier", self.add_folder),
            self._button("Retirer la sélection", self.remove_selected),
            self._button("Vider", self.clear_playlist),
        ]))

        self.sort_btn = QtWidgets.QPushButton("Trier ▾")
        self.sort_menu = QtWidgets.QMenu(self.sort_btn)
        for label, key, rev in self.SORT_CHOICES:
            act = self.sort_menu.addAction(label)
            act.triggered.connect(
                lambda checked=False, k=key, r=rev, l=label: self.sort_playlist(k, r, l))
        self.sort_menu.addSeparator()
        self.sort_menu.addAction("Inverser l'ordre actuel").triggered.connect(
            lambda checked=False: self.reverse_playlist())
        self.sort_btn.setMenu(self.sort_menu)

        layout.addLayout(self._row([
            self._button("Mélanger", self.shuffle_playlist),
            self.sort_btn,
            self._button("Enregistrer la playlist", self.save_playlist),
            self._button("Ouvrir une playlist", self.load_playlist),
        ]))

        # 3) Lecture
        self.play_btn = self._button("Lecture", self.toggle_play)
        layout.addLayout(self._row([
            self._button("Précédent", self.prev_item),
            self.play_btn,
            self._button("Stop", self.stop),
            self._button("Suivant", self.next_item),
        ]))

        # Vidéo : progression et volume
        self.seek_slider = ClickSlider()
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setEnabled(False)
        self.seek_slider.sliderPressed.connect(self._on_seek_pressed)
        self.seek_slider.sliderMoved.connect(self._on_seek_moved)
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        self.time_label = QtWidgets.QLabel("--:-- / --:--")
        self.time_label.setMinimumWidth(120)
        seek_row = QtWidgets.QHBoxLayout()
        seek_row.addWidget(QtWidgets.QLabel("Vidéo :"))
        seek_row.addWidget(self.seek_slider, 1)
        seek_row.addWidget(self.time_label)
        layout.addLayout(seek_row)

        self.volume_slider = ClickSlider()
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.volume)
        self.volume_slider.valueChanged.connect(self._on_volume)
        self.volume_label = QtWidgets.QLabel("100 %")
        self.volume_label.setMinimumWidth(50)
        self.mute_btn = QtWidgets.QPushButton("Muet")
        self.mute_btn.setCheckable(True)
        self.mute_btn.toggled.connect(self._on_mute)
        vol_row = QtWidgets.QHBoxLayout()
        vol_row.addWidget(QtWidgets.QLabel("Volume :"))
        vol_row.addWidget(self.volume_slider, 1)
        vol_row.addWidget(self.volume_label)
        vol_row.addWidget(self.mute_btn)
        layout.addLayout(vol_row)

        # 4) Viewer
        layout.addLayout(self._row([
            self._button("Ouvrir viewer", self.open_viewer),
            self._button("Fermer viewer", self.close_viewer),
            self._button("Plein écran", self.fullscreen_viewer),
        ]))

        # 5) Options
        self.photo_spin = QtWidgets.QSpinBox()
        self.photo_spin.setRange(1, 300)
        self.photo_spin.setValue(5)
        self.photo_spin.setSuffix(" s")

        self.orient_combo = QtWidgets.QComboBox()
        for label, angle in (("Normal (0°)", 0), ("Tourné à droite (90°)", 90),
                             ("Retourné (180°)", 180), ("Tourné à gauche (270°)", 270)):
            self.orient_combo.addItem(label, angle)
        self.orient_combo.currentIndexChanged.connect(self._on_orientation)
        self.list.itemSelectionChanged.connect(self._sync_orientation_combo)

        self.filter_combo = QtWidgets.QComboBox()
        for label, name in (("Aucun", "none"), ("Noir et blanc", "gray"), ("Flou", "blur")):
            self.filter_combo.addItem(label, name)
        self.filter_combo.currentIndexChanged.connect(self._on_filter)

        self.fade_spin = QtWidgets.QDoubleSpinBox()
        self.fade_spin.setRange(0.0, 3.0)
        self.fade_spin.setSingleStep(0.5)
        self.fade_spin.setDecimals(1)
        self.fade_spin.setValue(1.0)
        self.fade_spin.setSuffix(" s")
        self.fade_spin.setSpecialValueText("Aucun")

        self.loop_check = QtWidgets.QCheckBox("Boucle")
        self.loop_check.setChecked(True)

        opts = QtWidgets.QGridLayout()
        opts.addWidget(QtWidgets.QLabel("Durée des photos :"), 0, 0)
        opts.addWidget(self.photo_spin, 0, 1)
        opts.addWidget(self.loop_check, 0, 2)
        opts.addWidget(QtWidgets.QLabel("Filtre (photos) :"), 1, 0)
        opts.addWidget(self.filter_combo, 1, 1, 1, 2)
        opts.addWidget(QtWidgets.QLabel("Fondu entre photos :"), 2, 0)
        opts.addWidget(self.fade_spin, 2, 1)
        layout.addLayout(opts)

        orient_box = QtWidgets.QGroupBox("Orientation du fichier sélectionné (ou en cours de lecture)")
        orient_layout = QtWidgets.QVBoxLayout(orient_box)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel("Angle :"))
        top.addWidget(self.orient_combo, 1)
        orient_layout.addLayout(top)
        orient_layout.addLayout(self._row([
            self._button("Tourner à gauche", self.rotate_left),
            self._button("Tourner à droite", self.rotate_right),
            self._button("Appliquer cet angle à tous", self.apply_rotation_to_all),
        ]))
        layout.addWidget(orient_box)

        self.status = QtWidgets.QLabel("Prêt. Ajoutez des fichiers ou un dossier.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

    def set_status(self, text):
        self.status.setText(text)

    def _update_play_button(self):
        self.play_btn.setText("Pause" if self.state == "playing" else "Lecture")

    # --- playlist ------------------------------------------------------
    SORT_CHOICES = [
        ("Nom (A → Z)", "name", False),
        ("Nom (Z → A)", "name", True),
        ("Date de modification (la plus récente d'abord)", "mtime", True),
        ("Date de modification (la plus ancienne d'abord)", "mtime", False),
        ("Date de création (la plus récente d'abord)", "ctime", True),
        ("Date de création (la plus ancienne d'abord)", "ctime", False),
        ("Date d'ajout (dernier ajouté d'abord)", "added", True),
        ("Date d'ajout (premier ajouté d'abord)", "added", False),
        ("Taille (la plus grande d'abord)", "size", True),
        ("Taille (la plus petite d'abord)", "size", False),
        ("Type (images d'abord)", "type_img", False),
        ("Type (vidéos d'abord)", "type_vid", False),
    ]

    def _make_list_item(self, path):
        item = QtWidgets.QListWidgetItem(self._item_text(path))
        item.setToolTip(path)
        item.setData(QtCore.Qt.UserRole, path)
        return item

    def _append_items(self, files):
        known = set(self.items)
        added = 0
        for f in files:
            if f in known:
                continue
            known.add(f)
            self.items.append(f)
            self._add_counter += 1
            self.added[f] = self._add_counter
            self.list.addItem(self._make_list_item(f))
            added += 1
        return added

    def add_paths(self, paths):
        all_files, ignored = [], 0
        for path in paths:
            if os.path.isdir(path):
                files, ign = collect_folder(path)
                ignored += ign
            elif os.path.isfile(path):
                result = check_file(path)
                files = [path] if result == "ok" else []
                ignored += 1 if result == "ignore" else 0
            else:
                continue
            all_files.extend(files)
        added = self._append_items(all_files)
        self.set_status("%d fichier(s) ajouté(s), %d ignoré(s) (cachés ou de moins de 10 Ko). Total : %d."
                        % (added, ignored, len(self.items)))

    def handle_paths(self, paths):
        """Fichiers/dossiers déposés ou passés en argument (les .vidmix sont des playlists)."""
        playlists = [p for p in paths if p.lower().endswith(".vidmix")]
        others = [p for p in paths if not p.lower().endswith(".vidmix")]
        if others:
            self.add_paths(others)
        if playlists:
            self.open_playlist_path(playlists[0])

    def add_files(self):
        exts = " ".join("*" + e for e in sorted(IMAGE_EXT | VIDEO_EXT))
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "Choisir des images ou vidéos", "", "Médias (%s)" % exts)
        if files:
            self.add_paths(files)

    def add_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Choisir un dossier (sous-dossiers inclus)")
        if folder:
            self.add_paths([folder])

    def remove_selected(self):
        rows = sorted((self.list.row(i) for i in self.list.selectedItems()), reverse=True)
        if not rows:
            return
        current = self.items[self.index] if 0 <= self.index < len(self.items) else None
        for r in rows:
            self.added.pop(self.items[r], None)
            self.rotations.pop(self.items[r], None)
            del self.items[r]
            self.list.takeItem(r)
        if current in self.items:
            self.index = self.items.index(current)
        else:
            self.index = -1
            if self.state != "stopped":
                self.stop()
        self.set_status("%d fichier(s) retiré(s)." % len(rows))

    def clear_playlist(self):
        self.stop()
        self.items = []
        self.added = {}
        self.rotations = {}
        self.index = -1
        self.list.clear()
        self.set_status("Playlist vidée.")

    # --- ordre de la playlist ------------------------------------------
    def _current_path(self):
        if 0 <= self.index < len(self.items):
            return self.items[self.index]
        return None

    def _refresh_list(self):
        self.list.clear()
        for p in self.items:
            self.list.addItem(self._make_list_item(p))
        if self.state != "stopped" and 0 <= self.index < len(self.items):
            self.list.setCurrentRow(self.index)

    def _apply_order(self, new_items):
        current = self._current_path()
        self.items = list(new_items)
        self.index = self.items.index(current) if current in self.items else -1
        self._refresh_list()

    def _on_list_reordered(self):
        """Appelé après un glisser-déposer de lignes dans la playlist."""
        new_items = [self.list.item(i).data(QtCore.Qt.UserRole) for i in range(self.list.count())]
        if sorted(new_items) != sorted(self.items):  # sécurité : ne devrait jamais arriver
            self._refresh_list()
            return
        current = self._current_path()
        self.items = new_items
        self.index = self.items.index(current) if current in self.items else -1
        self.set_status("Ordre de la playlist modifié.")

    def shuffle_playlist(self):
        if len(self.items) < 2:
            self.set_status("Il faut au moins 2 fichiers pour mélanger.")
            return
        order = list(self.items)
        random.shuffle(order)
        self._apply_order(order)
        self.set_status("Playlist mélangée.")

    def _sort_key_func(self, key):
        if key == "name":
            return lambda p: natural_key(os.path.basename(p))
        if key == "mtime":
            return modified_time
        if key == "ctime":
            return creation_time
        if key == "added":
            return lambda p: self.added.get(p, 0)
        if key == "size":
            return file_size
        if key == "type_img":
            return lambda p: media_kind(p) != "image"
        return lambda p: media_kind(p) != "video"  # type_vid

    def sort_playlist(self, key, reverse, label=""):
        if len(self.items) < 2:
            return
        func = self._sort_key_func(key)
        order = sorted(self.items,
                       key=lambda p: (func(p), natural_key(os.path.basename(p))),
                       reverse=reverse)
        self._apply_order(order)
        self.set_status("Playlist triée : %s." % label if label else "Playlist triée.")

    def reverse_playlist(self):
        if len(self.items) < 2:
            return
        self._apply_order(list(reversed(self.items)))
        self.set_status("Ordre inversé.")

    # --- sauvegarde / ouverture d'une playlist ---------------------------
    def save_playlist(self):
        if not self.items:
            self.set_status("La playlist est vide : rien à enregistrer.")
            return
        default = os.path.join(os.path.expanduser("~"), "diaporama.vidmix")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Enregistrer la playlist", default, "Playlist VidMix (*.vidmix)")
        if path:
            self._write_playlist(path)

    def _write_playlist(self, path):
        if not path.lower().endswith(".vidmix"):
            path += ".vidmix"
        data = {
            "version": 1,
            "app": "VidMix",
            "items": list(self.items),
            "rotations": {p: a for p, a in self.rotations.items() if a and p in set(self.items)},
            "settings": {
                "photo_seconds": self.photo_spin.value(),
                "fade_seconds": self.fade_spin.value(),
                "filter": self.filter_name,
                "loop": self.loop_check.isChecked(),
            },
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            self.set_status("Impossible d'enregistrer la playlist : %s" % exc)
            return
        self.set_status("Playlist enregistrée (%d fichiers) : %s" % (len(self.items), path))

    def load_playlist(self):
        home = os.path.expanduser("~")
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Ouvrir une playlist", home,
            "Playlist VidMix (*.vidmix);;Tous les fichiers (*)")
        if path:
            self.open_playlist_path(path)

    def _ask_replace(self):
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle("Ouvrir une playlist")
        box.setText("Une playlist est déjà en cours. Que voulez-vous faire ?")
        b_replace = box.addButton("Remplacer", QtWidgets.QMessageBox.AcceptRole)
        b_append = box.addButton("Ajouter à la suite", QtWidgets.QMessageBox.AcceptRole)
        box.addButton("Annuler", QtWidgets.QMessageBox.RejectRole)
        box.exec_()
        clicked = box.clickedButton()
        if clicked is b_replace:
            return "replace"
        if clicked is b_append:
            return "append"
        return None

    def open_playlist_path(self, path):
        mode = "replace"
        if self.items:
            mode = self._ask_replace()
            if mode is None:
                return
        self.load_playlist_file(path, mode)

    def _apply_settings(self, st):
        if not isinstance(st, dict):
            return
        try:
            secs = int(st.get("photo_seconds", self.photo_spin.value()))
            self.photo_spin.setValue(max(1, min(300, secs)))
        except (TypeError, ValueError):
            pass
        try:
            fade = float(st.get("fade_seconds", self.fade_spin.value()))
            self.fade_spin.setValue(max(0.0, min(3.0, fade)))
        except (TypeError, ValueError):
            pass
        for combo, key in ((self.filter_combo, "filter"),):
            idx = combo.findData(st.get(key))
            if idx >= 0:
                combo.setCurrentIndex(idx)
        if isinstance(st.get("loop"), bool):
            self.loop_check.setChecked(st["loop"])

    def _load_rotations(self, data, files):
        """Remet l'angle de chaque fichier (anciennes playlists : un seul angle pour tous)."""
        wanted = data.get("rotations")
        if not isinstance(wanted, dict):
            settings = data.get("settings")
            legacy = settings.get("rotation") if isinstance(settings, dict) else None
            wanted = {p: legacy for p in files} if legacy in (90, 180, 270) else {}
        for p in files:
            angle = wanted.get(p)
            if isinstance(angle, int) and not isinstance(angle, bool) and angle in (90, 180, 270):
                self.rotations[p] = angle
        for row, p in enumerate(self.items):
            self.list.item(row).setText(self._item_text(p))

    def load_playlist_file(self, path, mode="replace"):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as exc:
            self.set_status("Playlist illisible : %s" % exc)
            return
        items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(items, list):
            self.set_status("Ce fichier n'est pas une playlist VidMix valide.")
            return

        valid, missing, ignored = [], 0, 0
        for p in items:
            if not isinstance(p, str):
                continue
            if not os.path.isfile(p):
                missing += 1
                continue
            if check_file(p) == "ok":
                valid.append(p)
            else:
                ignored += 1

        if mode == "replace":
            self.stop()
            self.items = []
            self.added = {}
            self.rotations = {}
            self.index = -1
            self.list.clear()
            self._apply_settings(data.get("settings"))
        known_before = set(self.items)
        new_files = [p for p in valid if p not in known_before]
        added = self._append_items(valid)
        self._load_rotations(data, new_files)
        msg = "Playlist chargée : %d fichier(s) ajouté(s)" % added
        if missing:
            msg += ", %d introuvable(s) (playlist créée sur un autre ordinateur ?)" % missing
        if ignored:
            msg += ", %d ignoré(s)" % ignored
        self.set_status(msg + ". Total : %d." % len(self.items))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        self.handle_paths(paths)

    # --- viewer --------------------------------------------------------
    def open_viewer(self):
        if not self.viewer.isVisible():
            self.viewer.move(self.x() + self.width() + 20, self.y())
            self.viewer.show()
        self.viewer.raise_()

    def close_viewer(self):
        self.viewer.close()

    def fullscreen_viewer(self):
        self.open_viewer()
        self.viewer.toggle_fullscreen()

    def _on_viewer_closed(self):
        self.stop()

    # --- options -------------------------------------------------------
    def rotation_of(self, path):
        return self.rotations.get(path, 0)

    def _item_text(self, path):
        kind = "IMG" if media_kind(path) == "image" else "VID"
        text = "[%s]  %s" % (kind, os.path.basename(path))
        angle = self.rotation_of(path)
        if angle:
            text += "   (%d°)" % angle
        return text

    def set_rotation(self, paths, angle):
        """Fixe l'angle (0, 90, 180, 270) de chaque fichier de la liste donnée."""
        angle = int(angle) % 360
        wanted = set(paths) & set(self.items)
        for p in wanted:
            if angle:
                self.rotations[p] = angle
            else:
                self.rotations.pop(p, None)
        for row, p in enumerate(self.items):
            if p in wanted:
                self.list.item(row).setText(self._item_text(p))
        return len(wanted)

    def _orientation_targets(self):
        """Fichiers concernés : ceux qui sont sélectionnés, sinon celui en cours."""
        rows = sorted(self.list.row(i) for i in self.list.selectedItems())
        if rows:
            return [self.items[r] for r in rows]
        current = self._current_path()
        return [current] if current else []

    def _sync_orientation_combo(self):
        targets = self._orientation_targets()
        angle = self.rotation_of(targets[0]) if targets else 0
        self.orient_combo.blockSignals(True)
        self.orient_combo.setCurrentIndex(max(0, self.orient_combo.findData(angle)))
        self.orient_combo.blockSignals(False)

    def _replay_current_if_in(self, targets, keep_rows=None):
        if self.state != "stopped" and self._current_path() in targets:
            self.play_index(self.index)   # la vidéo repart du début
            if keep_rows:
                self.list.clearSelection()
                for r in keep_rows:
                    self.list.item(r).setSelected(True)

    def _change_rotation(self, absolute=None, delta=0):
        targets = self._orientation_targets()
        if not targets:
            self.set_status("Sélectionnez d'abord un fichier dans la playlist.")
            self._sync_orientation_combo()
            return
        rows = [self.list.row(i) for i in self.list.selectedItems()]
        for p in targets:
            angle = absolute if absolute is not None else self.rotation_of(p) + delta
            self.set_rotation([p], angle)
        self._replay_current_if_in(targets, rows)
        self._sync_orientation_combo()
        self.set_status("Orientation modifiée pour %d fichier(s)." % len(targets))

    def _on_orientation(self):
        self._change_rotation(absolute=int(self.orient_combo.currentData()))

    def rotate_left(self):
        self._change_rotation(delta=-90)

    def rotate_right(self):
        self._change_rotation(delta=90)

    def apply_rotation_to_all(self):
        if not self.items:
            self.set_status("La playlist est vide.")
            return
        angle = int(self.orient_combo.currentData())
        self.set_rotation(list(self.items), angle)
        self._replay_current_if_in(list(self.items))
        self.set_status("Orientation %d° appliquée aux %d fichiers." % (angle, len(self.items)))

    def _on_filter(self):
        self.filter_name = self.filter_combo.currentData()
        if self.state != "stopped" and 0 <= self.index < len(self.items):
            if media_kind(self.items[self.index]) == "image":
                self.play_index(self.index)

    # --- lecture -------------------------------------------------------
    def toggle_play(self):
        if self.state == "stopped":
            if not self.items:
                self.set_status("La playlist est vide : ajoutez des fichiers d'abord.")
                return
            row = self.list.currentRow()
            self.play_index(row if row >= 0 else 0)
        elif self.state == "playing":
            self._pause()
        else:
            self._resume()

    def _pause(self):
        self.state = "paused"
        self.image_timer.stop()
        if self.vlc_player is not None and self._current_kind() == "video":
            self.vlc_player.set_pause(1)
        self._update_play_button()
        self.set_status("En pause.")

    def _resume(self):
        self.state = "playing"
        if self._current_kind() == "video":
            if self.vlc_player is not None:
                self.vlc_player.set_pause(0)
        else:
            self.image_timer.start(self.photo_spin.value() * 1000)
        self._update_play_button()
        self.set_status("Lecture.")

    def _current_kind(self):
        if 0 <= self.index < len(self.items):
            return media_kind(self.items[self.index])
        return None

    def play_index(self, i):
        self._stop_media()
        if not (0 <= i < len(self.items)):
            self.stop()
            return
        self.index = i
        self.list.clearSelection()  # evite que les anciennes lignes restent sélectionnées
        self.list.setCurrentRow(i)
        self.state = "playing"
        self._update_play_button()
        self.open_viewer()

        path = self.items[i]
        self.set_status("Lecture : %s  (%d/%d)" % (os.path.basename(path), i + 1, len(self.items)))
        if not os.path.isfile(path):
            self._skip_bad("Fichier introuvable : %s" % os.path.basename(path))
            return
        if media_kind(path) == "image":
            self._play_image(path)
        else:
            self._play_video(path)

    def _play_image(self, path):
        reader = QtGui.QImageReader(path)
        reader.setAutoTransform(True)  # respecte l'orientation des photos de téléphone
        img = reader.read()
        if img.isNull():
            self._skip_bad("Image illisible : %s" % os.path.basename(path))
            return
        if self.filter_name == "gray":
            img = img.convertToFormat(QtGui.QImage.Format_Grayscale8)
        elif self.filter_name == "blur":
            w, h = img.width(), img.height()
            small = img.scaled(max(1, w // 15), max(1, h // 15),
                               QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
            img = small.scaled(w, h, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
        pix = QtGui.QPixmap.fromImage(img)
        angle = self.rotation_of(path)
        if angle:
            pix = pix.transformed(QtGui.QTransform().rotate(angle),
                                  QtCore.Qt.SmoothTransformation)
        fade_ms = int(self.fade_spin.value() * 1000)
        self.viewer.show_pixmap(pix, fade_ms)
        self._fail_streak = 0
        # la photo reste entièrement visible pendant la durée choisie, le fondu s'y ajoute
        self.image_timer.start(self.photo_spin.value() * 1000 + fade_ms)

    def _play_video(self, path):
        if vlc is None:
            self._skip_bad("VLC est introuvable (installez VLC 64 bits). Détail : %s" % VLC_ERROR)
            return
        if not self._ensure_player(self.rotation_of(path)):
            self._skip_bad("Impossible de démarrer le lecteur vidéo VLC.")
            return
        self.viewer.show_video_surface()
        self._bind_player()
        self.vlc_player.set_media(self.vlc_instance.media_new(path))
        self.vlc_player.play()
        self._fail_streak = 0
        self._video_length = 0
        self._audio_pending = True
        self._apply_audio()
        self._set_video_controls(True)
        self.time_label.setText("0:00 / --:--")
        self.poll_timer.start()

    def _skip_bad(self, message):
        """Fichier impossible à lire : on le signale et on passe au suivant."""
        self._fail_streak += 1
        if self._fail_streak >= max(1, len(self.items)):
            self.stop()
            self.set_status(message + " — aucun fichier lisible, arrêt.")
            return
        self.set_status(message + " — passage au suivant.")
        self.image_timer.start(400)  # reutilise le minuteur : s'arrete avec Stop

    def _ensure_player(self, angle=0):
        # VLC fixe la rotation à la création du lecteur : on ne le recrée que si l'angle change
        if self.vlc_player is not None and self._player_rotation == angle:
            return True
        self._release_player()
        try:
            args = ["--no-video-title-show", "--quiet"]
            if angle:
                args += ["--video-filter=transform", "--transform-type=%d" % angle]
            self.vlc_instance = vlc.Instance(*args)
            self.vlc_player = self.vlc_instance.media_player_new()
            try:
                self.vlc_player.video_set_key_input(False)
                self.vlc_player.video_set_mouse_input(False)
            except Exception:
                pass
            self._player_rotation = angle
            return True
        except Exception:
            self.vlc_instance = None
            self.vlc_player = None
            return False

    def _bind_player(self):
        wid = int(self.viewer.video_frame.winId())
        if sys.platform.startswith("win"):
            self.vlc_player.set_hwnd(wid)
        elif sys.platform == "darwin":
            self.vlc_player.set_nsobject(wid)
        else:
            self.vlc_player.set_xwindow(wid)

    def _release_player(self):
        try:
            if self.vlc_player is not None:
                self.vlc_player.stop()
                self.vlc_player.release()
            if self.vlc_instance is not None:
                self.vlc_instance.release()
        except Exception:
            pass
        self.vlc_player = None
        self.vlc_instance = None

    # --- progression, volume ---------------------------------------------
    def _set_video_controls(self, enabled):
        self.seek_slider.setEnabled(enabled)
        if not enabled:
            self.seek_slider.setValue(0)
            self.time_label.setText("--:-- / --:--")
            self._video_length = 0
            self._seeking = False

    def _apply_audio(self):
        if self.vlc_player is None:
            return
        try:
            self.vlc_player.audio_set_volume(int(self.volume))
            self.vlc_player.audio_set_mute(1 if self.muted else 0)
        except Exception:
            pass

    def _on_volume(self, value):
        self.volume = int(value)
        self.volume_label.setText("%d %%" % self.volume)
        self._apply_audio()

    def _on_mute(self, checked):
        self.muted = bool(checked)
        self.mute_btn.setText("Son coupé" if self.muted else "Muet")
        self._apply_audio()

    def _step_volume(self, delta):
        self.volume_slider.setValue(max(0, min(100, self.volume + int(delta))))

    def _toggle_mute(self):
        self.mute_btn.toggle()

    def _on_seek_pressed(self):
        self._seeking = True

    def _on_seek_moved(self, value):
        if self._video_length > 0:
            self.time_label.setText("%s / %s" % (
                fmt_time(self._video_length * value / 1000.0), fmt_time(self._video_length)))

    def _on_seek_released(self):
        self._seeking = False
        if (self.vlc_player is not None and self.state != "stopped"
                and self._current_kind() == "video"):
            try:
                self.vlc_player.set_position(self.seek_slider.value() / 1000.0)
            except Exception:
                pass

    def _seek_relative(self, delta_ms):
        if (self.vlc_player is None or self.state == "stopped"
                or self._current_kind() != "video"):
            return
        try:
            length = self.vlc_player.get_length()
            if length <= 0:
                return
            target = max(0, min(length - 500, self.vlc_player.get_time() + int(delta_ms)))
            self.vlc_player.set_time(int(target))
        except Exception:
            pass

    def _poll_video(self):
        if (self.vlc_player is None or self.state == "stopped"
                or self._current_kind() != "video"):
            return
        st = self.vlc_player.get_state()
        if st == vlc.State.Playing and self._audio_pending:
            self._apply_audio()   # VLC n'accepte le volume qu'une fois la lecture démarrée
            self._audio_pending = False
        try:
            length = self.vlc_player.get_length()
            current = self.vlc_player.get_time()
        except Exception:
            length, current = 0, 0
        if length and length > 0:
            self._video_length = length
            if not self._seeking:
                self.seek_slider.setValue(int(max(0, min(length, current)) * 1000 / length))
                self.time_label.setText("%s / %s" % (fmt_time(current), fmt_time(length)))
        if self.state == "playing":
            if st == vlc.State.Ended:
                self.poll_timer.stop()
                self.next_item()
            elif st == vlc.State.Error:
                self.poll_timer.stop()
                self._skip_bad("Vidéo illisible")

    def _stop_media(self):
        self.image_timer.stop()
        self.poll_timer.stop()
        self._set_video_controls(False)
        if self.vlc_player is not None:
            try:
                self.vlc_player.stop()
            except Exception:
                pass

    def stop(self):
        self._stop_media()
        self.state = "stopped"
        self._update_play_button()
        self.viewer.clear()
        self.set_status("Arrêté.")

    def next_item(self):
        if not self.items:
            return
        nxt = self.index + 1
        if nxt >= len(self.items):
            if self.loop_check.isChecked():
                nxt = 0
            else:
                self.stop()
                self.set_status("Fin de la playlist.")
                return
        self.play_index(nxt)

    def prev_item(self):
        if not self.items:
            return
        prv = self.index - 1
        if prv < 0:
            prv = len(self.items) - 1
        self.play_index(prv)

    # --- fermeture -----------------------------------------------------
    def closeEvent(self, event):
        self._stop_media()
        self._release_player()
        self.viewer.blockSignals(True)
        self.viewer.close()
        event.accept()


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = VidMixWindow()
    win.show()
    if len(sys.argv) > 1:
        win.handle_paths(sys.argv[1:])
    if vlc is None:
        QtWidgets.QMessageBox.warning(
            win, "VLC introuvable",
            "Le lecteur VLC n'a pas été trouvé : les images fonctionneront, "
            "mais pas les vidéos.\n\nInstallez VLC (version 64 bits) depuis videolan.org.\n\n"
            "Détail : %s" % VLC_ERROR)
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
