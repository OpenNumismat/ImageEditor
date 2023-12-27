[![GitHub release](https://img.shields.io/github/release/opennumismat/ImageEditor.svg)](https://github.com/opennumismat/ImageEditor/releases/)
[![GitHub release (latest by date)](https://img.shields.io/github/downloads/opennumismat/ImageEditor/latest/total.svg)](https://hanadigital.github.io/grev/?user=OpenNumismat&repo=ImageEditor)
[![GitHub all releases](https://img.shields.io/github/downloads/opennumismat/ImageEditor/total.svg)](https://hanadigital.github.io/grev/?user=OpenNumismat&repo=ImageEditor)
[![GitHub license](https://img.shields.io/github/license/opennumismat/ImageEditor.svg)](https://github.com/opennumismat/ImageEditor/blob/master/LICENSE)
 
# ImageEditor

ImageEditor is a part of [OpenNumismat](http://opennumismat.github.io/) project, so it aims to edit coins images.

![Screenshot](https://opennumismat.github.io/images/imageEdit.png)
![Screenshot](https://opennumismat.github.io/images/imageEdit1.png)

#### Features

* Support popular image formats: JPEG, PNG, BMP, TIFF, GIF, WebP
* Full Screen mode
* Image editing tools: resize, rotate, crop (rectangle, ellipse, perspective transformation)
* Up to 10 Undo/Redo actions
* Single click to switch between best fit and actual size mode
* Mouse wheel zoom
* Portable version - can be run from a removable storage device
* Multilanguage: Bulgarian, English, German, Russian, Portuguese, Spanish, Ukrainian

##### Keyboard Shortcuts

`Ctrl`+`O` - Open file  
`Ctrl`+`S` - Save  
`Ctrl`+`C`, `Ctrl`+`Insert` - Copy  
`Ctrl`+`V`, `Shift`+`Insert` - Paste  
`Ctrl`+`Z` - Undo  
`Ctrl`+`Y` - Redo  
`Ctrl`+`Right` - Rotate to right  
`Ctrl`+`Left` - Rotate to left  
`C` - Open crop tool  
`R` - Open rotate tool  
`+` - Zoom in  
`-` - Zoom out  
`0` - Fit to window  
`1`, `A` - Scale 100%  
`2` - Scale 200%  
`3` - Scale 300%  
`4` - Scale 400%  
`5` - Scale 500%  
`6` - Scale 600%  
`F11` - Full screen  
`Esc` - Quit  

#### Download
[Latest version for Windows 10 and later](https://github.com/OpenNumismat/ImageEditor/releases/latest)

#### For run from source code
    pip3 install -r requirements.txt
    python3 src/run.py [<image_file_name>]
