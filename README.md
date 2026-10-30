# TagGUI-Next

<img src='icon.png' alt='TagGUI-Next icon' width='128'>

**TagGUI-Next** is a fast, modern, and self-contained local dataset manager and tagger built with **PySide6**, **PyTorch**, and **timm**. Designed to replace the aging [TagGUI](https://github.com/jhc13/taggui)  and [BooruDatasetTagManager](https://github.com/starik222/BooruDatasetTagManager) , in my personal workflows. It provides an intuitive HTML5/JavaScript GUI powered by `QWebChannel` for effortless tagging, bulk editing, and dataset organization for machine learning models (such as Stable Diffusion).

**TagGUI-Next** by default uses SmilingWolf / wd-eva02-large-tagger-v3 for an image interrogator. It's best for danbooru/e621 style tags, useful in preparation of image datasets for LoRa Training (for Pony XL v6/ Illustrious/ NoobAi and SDXL 1.0).

**TagGUI-Next** is tested to work with masive models like BLIP-2

---

<img src='assets/TagGUI-Next.png' alt='TagGUI-Next' width='100%'>


## Key Features

- **Local PyTorch Tagger**: Powered by local models (like `wd-eva02-large-tagger-v3`) with full CUDA 13 support—no external API servers required.
- **Modern HTML5/JS GUI**: Clean, responsive, dark-themed interface running smoothly via Qt WebEngine.
- **Advanced Tag Management**:
  - Global tag list with usage counts and search/filter.
  - Double-click to rename tags globally across all images.
  - Drag-and-drop tag reordering on active images.
  - Multi-select support (Shift+Click and Ctrl+Click).
- **Keyword & Strategy Management**: 
  - Define custom training keywords that prepend and auto-sort.
  - Configure AutoTag behavior to either **Add** or **Replace** existing tags via a built-in Settings modal.
- **Token Estimation**: Real-time context token counter with visual warning thresholds for prompt limits (e.g., 75 tokens).
- ** Robust Undo/Redo History**: Comprehensive history stack supporting `Ctrl+Z` and `Ctrl+Shift+Z` across tag edits, additions, and deletions.
- **Comprehensive Keyboard Shortcuts**: Fast navigation and workflow control using arrow keys, shortcuts, and batch selection.

---
## Controls

- Arrow Keys,Navigate through dataset images
- Shift + Click,Multi-select range of images / add tag to selection
- Ctrl + Click on a tag,adds keyword to the keyword list
- Ctrl + Alt + Click on a tag, removes keyword to the keyword list
- Shift + Click on a global tag (the left tag list), adds the tag to the image tags
- Shift+ Alt + Click on a global tag (the left tag list), removes the tag from the image tags
- double click on a tag opens an edit tag window.
- drag-and-drop image tags in the right panel to re-order them
- Delete / Backspace,Delete selected global tag from all images
- Escape,Clear filters and selections
- Ctrl + Z / Ctrl + Shift +Z , Undo/Redo commands
    
---
## Usage

Load the directory containing your images Dataset by clicking the `Open Dataset`
button in the top right of the window. Tags are loaded from `.txt` files in the directory with the same names as the
images.Any changes you make to the tags are also automatically saved to these `.txt`
files.

## Automatic Captioning

In addition to manual tagging, you can automatically generate captions or tags
for your images inside ***TagGUI-Next***.

The default image interrogator is [SmilingWolf's](https://huggingface.co/SmilingWolf) [(wd-eva02-large-tagger-v3)](https://huggingface.co/SmilingWolf/wd-eva02-large-tagger-v3) model,
It will be downloaded automatically on the first use (about 1.2GB, be patient and wait it to be instaled)

GPU generation requires a compatible NVIDIA GPU, the CPU generation is also
supported as a fallback.

To use the feature, select the images you want to caption in the image list,
then click the AutoTag button.

To change the interrogator settings click the settings button 
>
<img src='assets/TagGUI-Next_settings.png' alt='TagGUI-Next settings' width='100%'>

---
##  Pro-Tip for Massive Models (BLIP-2 / Qwen 7B)
If your GPU has limited VRAM (e.g., 8GB or 12GB), running massive 7B-parameter captioning models alongside PySide6/WebEngine can easily hit out-of-memory (OOM) limits. If you experience freezes or crashes with larger vision models, consider:

- Using smaller, lightweight alternatives like Moondream2 (vikhyatk/moondream2) or Florence-2-base (microsoft/Florence-2-base-ft) which load lightning-fast and run comfortably under 4–6GB VRAM.

- Keeping the SmilingWolf Taggers for fast, high-performance tag management

---
## Installation & Setup

**Clone the repository:**
   ```bash
     git clone https://github.com/ViTa-Plane/taggui-next.git
     cd taggui-next
  ```
- run install.bat to automatically set the python_embeded and to  install the requirements (about 3.72GB)
- start the TagGUI-Next with run.bat
- on first use, the auto-tagger will download the default interrogator [(wd-eva02-large-tagger-v3)](https://huggingface.co/SmilingWolf/wd-eva02-large-tagger-v3) to the local huggingface hub directory (about 1.2GB)
- it's tested on Python 3.13.15 ,torch 2.14.1+cu130, torchvision 0.29.1+cu130
    

