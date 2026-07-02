"""
DJK Clean — coffre-fort à médias
----------------------------------
Bouton "Nettoyer" : déplace tous les médias de la galerie vers un dossier
caché (corbeille externe) et les retire de l'index de la galerie Android.

Barre de recherche : tape "etienne" pour faire apparaître le bouton
"Restaurer" qui remet tout dans la galerie.

IMPORTANT : rien n'est jamais supprimé définitivement. Les fichiers sont
seulement déplacés + démasqués/remasqués. Pense à faire une sauvegarde
séparée si tu veux une vraie sécurité (batterie déchargée, tel perdu, etc).
"""

import os
import time
import shutil
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.clock import Clock
from kivy.properties import StringProperty, BooleanProperty

# ---------------------------------------------------------------------
# Détection Android (pour ne pas planter si on teste sur PC pendant le dev)
# ---------------------------------------------------------------------
try:
    from android.permissions import request_permissions, Permission
    from android.storage import primary_external_storage_path
    from jnius import autoclass
    ON_ANDROID = True
except ImportError:
    ON_ANDROID = False

MOT_SECRET = "etienne"  # mot déclencheur pour révéler "Restaurer"

# Dossiers ciblés pour le nettoyage (dossiers médias classiques)
DOSSIERS_MEDIAS = ["DCIM", "Pictures", "Movies", "WhatsApp/Media"]
NOM_CORBEILLE = ".djk_corbeille"


def chemin_stockage():
    if ON_ANDROID:
        return primary_external_storage_path()
    # Fallback pour tester sur PC pendant le développement
    return os.path.expanduser("~/djk_clean_test/storage")


def chemin_corbeille():
    return os.path.join(chemin_stockage(), NOM_CORBEILLE)


# ---------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------
def demander_permissions(callback=None):
    if not ON_ANDROID:
        if callback:
            callback(True)
        return

    perms = [
        Permission.READ_MEDIA_IMAGES,
        Permission.READ_MEDIA_VIDEO,
    ]

    def on_result(permissions, grants):
        if callback:
            callback(all(grants))

    request_permissions(perms, on_result)

    # MANAGE_EXTERNAL_STORAGE (Android 11+) ne peut pas être demandée comme
    # une permission classique — il faut rediriger l'utilisateur vers les
    # réglages système dédiés.
    if not verifie_manage_storage():
        ouvrir_reglages_manage_storage()


def verifie_manage_storage():
    if not ON_ANDROID:
        return True
    Environment = autoclass('android.os.Environment')
    return Environment.isExternalStorageManager()


def ouvrir_reglages_manage_storage():
    if not ON_ANDROID:
        return
    Intent = autoclass('android.content.Intent')
    Settings = autoclass('android.provider.Settings')
    Uri = autoclass('android.net.Uri')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    activity = PythonActivity.mActivity

    intent = Intent(Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION)
    uri = Uri.parse("package:" + activity.getPackageName())
    intent.setData(uri)
    activity.startActivity(intent)


# ---------------------------------------------------------------------
# Rescan MediaStore (pour que la galerie "oublie" ou "redécouvre" un fichier)
# ---------------------------------------------------------------------
def rescanner_fichier(chemin):
    if not ON_ANDROID:
        return
    MediaScannerConnection = autoclass('android.media.MediaScannerConnection')
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    activity = PythonActivity.mActivity
    MediaScannerConnection.scanFile(
        activity, [chemin], None, None
    )


# ---------------------------------------------------------------------
# Logique métier : nettoyer / restaurer
# ---------------------------------------------------------------------
EXTENSIONS_MEDIA = (
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic",
    ".mp4", ".mov", ".mkv", ".3gp", ".avi"
)


def lister_medias():
    """Retourne la liste des chemins de fichiers médias trouvés."""
    trouves = []
    base = chemin_stockage()
    for dossier in DOSSIERS_MEDIAS:
        chemin_dossier = os.path.join(base, dossier)
        if not os.path.isdir(chemin_dossier):
            continue
        for racine, _, fichiers in os.walk(chemin_dossier):
            if NOM_CORBEILLE in racine:
                continue
            for f in fichiers:
                if f.lower().endswith(EXTENSIONS_MEDIA):
                    trouves.append(os.path.join(racine, f))
    return trouves


def nettoyer_galerie(progress_callback=None):
    """Déplace tous les médias trouvés vers la corbeille cachée."""
    corbeille = chemin_corbeille()
    os.makedirs(corbeille, exist_ok=True)

    # .nomedia empêche Android d'indexer ce dossier dans la galerie
    nomedia_path = os.path.join(corbeille, ".nomedia")
    if not os.path.exists(nomedia_path):
        open(nomedia_path, "w").close()

    medias = lister_medias()
    total = len(medias)
    deplaces = 0

    # fichier de correspondance pour pouvoir restaurer au bon endroit
    manifest_path = os.path.join(corbeille, "_manifest.txt")
    manifest = []

    horodatage = int(time.time() * 1000)
    for i, chemin_source in enumerate(medias):
        nom_fichier = os.path.basename(chemin_source)
        destination = os.path.join(corbeille, f"{horodatage}_{i}__{nom_fichier}")
        try:
            shutil.move(chemin_source, destination)
            manifest.append(f"{destination}|{chemin_source}")
            rescanner_fichier(chemin_source)  # informe Android que le fichier a disparu
            deplaces += 1
        except Exception as e:
            print(f"Erreur déplacement {chemin_source}: {e}")

        if progress_callback:
            progress_callback(i + 1, total)

    with open(manifest_path, "a") as m:
        m.write("\n".join(manifest) + "\n")

    return deplaces, total


def restaurer_galerie(progress_callback=None):
    """Remet tous les fichiers de la corbeille à leur emplacement d'origine."""
    corbeille = chemin_corbeille()
    manifest_path = os.path.join(corbeille, "_manifest.txt")

    if not os.path.exists(manifest_path):
        return 0, 0

    with open(manifest_path, "r") as m:
        lignes = [l.strip() for l in m.readlines() if l.strip()]

    total = len(lignes)
    restaures = 0
    lignes_restantes = []

    for i, ligne in enumerate(lignes):
        try:
            source, destination_originale = ligne.split("|")
            os.makedirs(os.path.dirname(destination_originale), exist_ok=True)
            shutil.move(source, destination_originale)
            rescanner_fichier(destination_originale)  # réintègre dans la galerie
            restaures += 1
        except Exception as e:
            print(f"Erreur restauration {ligne}: {e}")
            lignes_restantes.append(ligne)

        if progress_callback:
            progress_callback(i + 1, total)

    # on ne garde que les lignes qui ont échoué (pour ne pas les perdre)
    with open(manifest_path, "w") as m:
        m.write("\n".join(lignes_restantes) + "\n")

    return restaures, total


# ---------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------
KV = """
ScreenManager:
    MainScreen:

<MainScreen>:
    name: "main"
    canvas.before:
        Color:
            rgba: 0.04, 0.06, 0.11, 1
        Rectangle:
            pos: self.pos
            size: self.size

    BoxLayout:
        orientation: "vertical"
        padding: dp(24)
        spacing: dp(16)

        Label:
            text: "DJK Clean"
            font_size: "26sp"
            bold: True
            size_hint_y: None
            height: dp(50)
            color: 0.95, 0.93, 0.90, 1

        TextInput:
            id: barre_recherche
            hint_text: "Rechercher"
            size_hint_y: None
            height: dp(48)
            multiline: False
            on_text: root.on_recherche_changee(self.text)
            background_color: 0.09, 0.12, 0.18, 1
            foreground_color: 0.95, 0.93, 0.90, 1
            padding: [dp(12), dp(12)]

        Label:
            id: statut_label
            text: root.statut
            size_hint_y: None
            height: dp(30)
            color: 0.6, 0.65, 0.7, 1
            font_size: "13sp"

        Widget:
            size_hint_y: 1

        Button:
            text: "Nettoyer"
            size_hint_y: None
            height: dp(56)
            background_color: 0.95, 0.66, 0.23, 1
            on_release: root.lancer_nettoyage()

        Button:
            id: bouton_restaurer
            text: "Restaurer"
            size_hint_y: None
            height: dp(56) if root.afficher_restaurer else 0
            opacity: 1 if root.afficher_restaurer else 0
            disabled: not root.afficher_restaurer
            background_color: 0.24, 0.85, 0.63, 1
            on_release: root.lancer_restauration()
"""


class MainScreen(Screen):
    statut = StringProperty("Prêt.")
    afficher_restaurer = BooleanProperty(False)

    def on_recherche_changee(self, texte):
        self.afficher_restaurer = (texte.strip().lower() == MOT_SECRET)

    def lancer_nettoyage(self):
        self.statut = "Vérification des permissions..."

        def apres_permissions(accorde):
            if not accorde:
                self.statut = "Permissions refusées."
                return
            self.statut = "Nettoyage en cours..."

            def progression(fait, total):
                self.statut = f"Nettoyage... {fait}/{total}"

            def apres_travail(dt):
                deplaces, total = nettoyer_galerie(progression)
                self.statut = f"Terminé — {deplaces}/{total} médias cachés."

            Clock.schedule_once(apres_travail, 0.2)

        demander_permissions(apres_permissions)

    def lancer_restauration(self):
        self.statut = "Restauration en cours..."

        def progression(fait, total):
            self.statut = f"Restauration... {fait}/{total}"

        def apres_travail(dt):
            restaures, total = restaurer_galerie(progression)
            self.statut = f"Terminé — {restaures}/{total} médias restaurés."
            self.ids.barre_recherche.text = ""

        Clock.schedule_once(apres_travail, 0.2)


class DJKCleanApp(App):
    def build(self):
        return Builder.load_string(KV)


if __name__ == "__main__":
    DJKCleanApp().run()
