# Magouille met en page

Petit logiciel de mise en page libre (licence MIT), en Python avec Qt (PySide6).
Pensé pour l'atelier et la formation : zines, livrets, affiches, export PDF prêt à imprimer.

## Ce qu'il sait faire
- Documents multipages, pages en vis-à-vis, marges, colonnes, fonds perdus
- Blocs texte, image, rectangle, ellipse ; magnétisme sur marges, colonnes et autres blocs
- Rotation des blocs (poignée ou angle exact), aussi dans le PDF
- Saisie du texte directement sur la page (curseur, sélection, copier-coller, accents), ou dans un éditeur à côté
- Texte chaîné d'un bloc à l'autre, texte en excès signalé
- Styles de paragraphe (police, corps, interlignage, alignement, retrait, espacements, approche, capitales, césure française)
- Styles de caractère (police, graisse, italique, corps, couleur, approche, capitales, souligné)
- Gabarits avec folio automatique (`{n}` = numéro de page, `{t}` = nombre de pages)
- Nuancier CMJN / RVB : le PDF est écrit en CMJN
- Polices fournies (SIL OFL), polices du système, polices importées (rangées dans le projet)
- Résolution effective des images, contrôle avant impression
- Export PDF vectoriel : polices incorporées, fonds perdus, traits de coupe, TrimBox/BleedBox
- Sauvegarde automatique de la dernière session

## Lancer depuis les sources
    pip install -r requirements.txt
    python main.py

## Fabriquer l'appli à double-cliquer
- Windows : double-clic sur `construire_windows.bat` → `dist\Magouille met en page.exe`
- Mac : `./construire_mac.sh` → `dist/Magouille met en page.app`
- Sur GitHub, pour tous les systèmes d'un coup : onglet Actions → « Construire l'appli » → Run workflow. On récupère les versions Windows, Mac (puces M et Intel) et Linux en bas de la page du résultat.
- Pour publier une version : créer un tag `v1.2` (par exemple). GitHub construit tout et range les fichiers dans une Release.

## Installer
- Windows : lancer le `.exe`. Si Windows affiche « Windows a protégé votre ordinateur », cliquer sur « Informations complémentaires » puis « Exécuter quand même ».
- Mac : dézipper, glisser l'appli dans Applications. Au premier lancement : clic droit sur l'appli → Ouvrir → Ouvrir (l'appli n'est pas signée par Apple).
- Linux : décompresser le `.tar.gz` puis lancer `Magouille met en page`. Sur Ubuntu/Debian, si elle ne s'ouvre pas : `sudo apt install libxcb-cursor0`.
