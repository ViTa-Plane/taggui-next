let backend = null;
let datasetImages = [];
let filteredImages = [];
let selectedImageIndex = null;
let multiSelectedIndices = new Set();
let lastClickedIndex = null;
let keywordsCombo = null;
let selectedLeftTag = null;
let availableInterrogators = [];
let selectedActiveTagIndex = null; // Track selected tag in right panel

let undoStack = [];
let redoStack = [];
const MAX_HISTORY = 50;

let currentSettingsData = {
    keywords: "",
    keyword_groups: {
        "general": ["masterpiece", "best quality"],
        "characters": ["1girl", "solo"]
    },
    model_name: "SmilingWolf/wd-eva02-large-tagger-v3",
    general_threshold: 0.35,
    character_threshold: 0.85,
    general_mcut_enabled: false,
    character_mcut_enabled: false,
    tag_strategy: "add",
    task_command: "<CAPTION>",
    custom_commands: [],
    thinking_mode: false,
    temperature: 0.7,
    top_p: 0.8,
    top_k: 20
};

// DOM Elements (declared cleanly)
let tagInput = null;
let autoBox = null;
let e621ToggleCb = null;

function getSelectedIndices() {
    const set = new Set(multiSelectedIndices);
    if (selectedImageIndex !== null) {
        set.add(selectedImageIndex);
    }
    return Array.from(set).filter(idx => idx !== null && idx >= 0);
}

// Delegates to native Python PyQt6 EditPromptDialog
function openEditTagModal(title, initialValue, onSave) {
    if (backend && typeof backend.openNativeEditPromptDialog === 'function') {
        backend.openNativeEditPromptDialog(title, initialValue, function(newText) {
            if (newText) {
                onSave(newText);
            }
        });
    }
}

function openSettingsModal() {
    if (backend && typeof backend.openNativeSettingsDialog === 'function') {
        backend.openNativeSettingsDialog();
    }
}

function openHelpModal() {
    document.body.classList.add('modal-open');
    document.getElementById('help-modal').style.display = 'flex';
}

function closeHelpModal() {
    document.body.classList.remove('modal-open');
    document.getElementById('help-modal').style.display = 'none';
}

function cleanImageTags(tags) {
    if (!Array.isArray(tags)) return [];
    const seen = new Set();
    return tags.filter(tag => {
        const trimmed = tag.trim();
        const lower = trimmed.toLowerCase();
        if (!lower) return false;
        if (seen.has(lower)) return false;
        seen.add(lower);
        return true;
    });
}

function addTagToImage(img, tag) {
    const trimmed = tag.trim();
    if (!trimmed) return false;
    const lower = trimmed.toLowerCase();
    const exists = img.tags.some(t => t.trim().toLowerCase() === lower);
    if (!exists) {
        img.tags.push(trimmed);
        return true;
    }
    return false;
}

function fetchDatasetSettings() {
    if (!backend) return;
    backend.getDatasetSettings(function(settingsRes) {
        applyLoadedSettings(settingsRes);
    });
}

function applyLoadedSettings(settingsRes) {
    try {
        currentSettingsData = JSON.parse(settingsRes);

        if (keywordsCombo) {
            const groups = currentSettingsData.keyword_groups || { "general": ["masterpiece", "best quality"], "characters": ["1girl", "solo"] };

            const selectedIdx = keywordsCombo.selectedIndex;
            let activeGroupKey = null;

            if (keywordsCombo.options.length > 0 && selectedIdx >= 0) {
                const groupNames = Object.keys(groups);
                if (selectedIdx < groupNames.length) {
                    activeGroupKey = groupNames[selectedIdx];
                }
            }

            let optionsHTML = '';
            let firstSelectableVal = '';
            let firstValidFound = false;
            let restoredVal = null;

            const groupEntries = Object.entries(groups);
            groupEntries.forEach(([groupName, tagsList]) => {
                const groupLabel = groupName.charAt(0).toUpperCase() + groupName.slice(1);
                const tagsStr = Array.isArray(tagsList) ? tagsList.join(', ') : tagsList;

                optionsHTML += `<option value="${tagsStr}" style="color: #cbd5e1; background: #181a24;"><span style="color: #16a47e; font-weight: bold;">${groupLabel}</span>: ${tagsStr}</option>`;

                if (!firstValidFound) {
                    firstSelectableVal = tagsStr;
                    firstValidFound = true;
                }

                if (activeGroupKey && groupName.toLowerCase() === activeGroupKey.toLowerCase()) {
                    restoredVal = tagsStr;
                }
            });

            keywordsCombo.innerHTML = optionsHTML;

            if (restoredVal !== null) {
                keywordsCombo.value = restoredVal;
            } else if (currentSettingsData.keywords && Array.from(keywordsCombo.options).some(opt => opt.value === currentSettingsData.keywords)) {
                keywordsCombo.value = currentSettingsData.keywords;
            } else if (firstSelectableVal) {
                keywordsCombo.value = firstSelectableVal;
            }

            currentSettingsData.keywords = keywordsCombo.value;
        }

        if (e621ToggleCb) e621ToggleCb.checked = !!currentSettingsData.use_e621;
    } catch(e) {
        currentSettingsData = { keywords: "", keyword_groups: {}, use_e621: false };
    }
    updateDatasetUI();
}

function browseFolder() {
    if (!backend) return;
    backend.browseDatasetFolder(function(response) {
        if (!response) return;
        datasetImages = JSON.parse(response);
        datasetImages.forEach(img => {
            img.tags = cleanImageTags(img.tags);
        });
        filteredImages = [...datasetImages];
        document.getElementById('image-grid').innerHTML = '';
        selectedImageIndex = null;
        multiSelectedIndices.clear();
        selectedLeftTag = null;
        undoStack = [];

        fetchDatasetSettings();
    });
}

function fetchDataset() {
    if (!backend) return;
    backend.getDatasetImages(function(response) {
        datasetImages = JSON.parse(response);
        datasetImages.forEach(img => {
            img.tags = cleanImageTags(img.tags);
        });
        filteredImages = [...datasetImages];

        fetchDatasetSettings();
    });
}

function pushUndoState() {
    const snapshot = {
        images: datasetImages.map(img => ({
            relative_path: img.relative_path,
            tags: [...img.tags]
        })),
        keywords: keywordsCombo ? keywordsCombo.value : "",
        selectedImageIndex: selectedImageIndex
    };
    undoStack.push(snapshot);
    if (undoStack.length > MAX_HISTORY) undoStack.shift();
    redoStack = [];
}

function performUndo() {
    if (undoStack.length === 0) return;
    const currentState = {
        images: datasetImages.map(img => ({
            relative_path: img.relative_path,
            tags: [...img.tags]
        })),
        keywords: keywordsCombo ? keywordsCombo.value : "",
        selectedImageIndex: selectedImageIndex
    };
    redoStack.push(currentState);
    applyState(undoStack.pop());
}

function performRedo() {
    if (redoStack.length === 0) return;
    const currentState = {
        images: datasetImages.map(img => ({
            relative_path: img.relative_path,
            tags: [...img.tags]
        })),
        keywords: keywordsCombo ? keywordsCombo.value : "",
        selectedImageIndex: selectedImageIndex
    };
    undoStack.push(currentState);
    applyState(redoStack.pop());
}

function applyState(targetState) {
    const batchUpdates = {};

    let targetSelectedPath = null;
    if (targetState.selectedImageIndex !== null && targetState.images[targetState.selectedImageIndex]) {
        targetSelectedPath = targetState.images[targetState.selectedImageIndex].relative_path;
    }

    const currentPaths = new Set(datasetImages.map(img => img.relative_path));
    const missingPaths = targetState.images.filter(prevImg => !currentPaths.has(prevImg.relative_path));

    if (missingPaths.length > 0) {
        missingPaths.forEach(prevImg => {
            if (backend) backend.restoreImageAndTags(prevImg.relative_path);
        });
        targetState.images.forEach(prevImg => {
            batchUpdates[prevImg.relative_path] = prevImg.tags.join(', ');
        });
        if (keywordsCombo) keywordsCombo.value = targetState.keywords;
        if (backend) {
            backend.saveBatchImageTags(JSON.stringify(batchUpdates));
            if (keywordsCombo) {
                currentSettingsData.keywords = keywordsCombo.value;
                backend.saveDatasetSettings(JSON.stringify(currentSettingsData));
            }
        }
        backend.getDatasetImages(function(response) {
            datasetImages = JSON.parse(response);
            datasetImages.forEach(img => img.tags = cleanImageTags(img.tags));
            applyFilter();

            if (targetSelectedPath) {
                const idx = datasetImages.findIndex(img => img.relative_path === targetSelectedPath);
                if (idx !== -1) selectImage(idx, true);
            }
        });
    } else {
        targetState.images.forEach(prevImg => {
            const img = datasetImages.find(i => i.relative_path === prevImg.relative_path);
            if (img) {
                img.tags = cleanImageTags([...prevImg.tags]);
                batchUpdates[prevImg.relative_path] = img.tags.join(', ');
            }
        });
        if (keywordsCombo) keywordsCombo.value = targetState.keywords;
        if (backend) {
            backend.saveBatchImageTags(JSON.stringify(batchUpdates));
            if (keywordsCombo) {
                currentSettingsData.keywords = keywordsCombo.value;
                backend.saveDatasetSettings(JSON.stringify(currentSettingsData));
            }
        }
        applyFilter();

        if (targetSelectedPath) {
            const idx = datasetImages.findIndex(img => img.relative_path === targetSelectedPath);
            if (idx !== -1) {
                selectImage(idx, true);
            }
        }
    }
}

// Connect via QWebChannel first, then setup all event listeners and fetch dataset
new QWebChannel(qt.webChannelTransport, function(channel) {
    backend = channel.objects.backend;

    // Initialize DOM element references
    keywordsCombo = document.getElementById('keywords-combo');
    tagInput = document.getElementById('tag-input');
    autoBox = document.getElementById('autocomplete-box');
    e621ToggleCb = document.getElementById('e621-toggle-cb');

    if (keywordsCombo) {
        keywordsCombo.addEventListener('change', function() {
            renderActiveTags();
            renderGlobalTagsList();
            if (backend) {
                currentSettingsData.keywords = this.value;
                backend.saveDatasetSettings(JSON.stringify(currentSettingsData));
            }
        });

        keywordsCombo.addEventListener('contextmenu', function(e) {
            e.preventDefault();
            if (backend && typeof backend.openNativeKeywordGroupsDialog === 'function') {
                backend.openNativeKeywordGroupsDialog();
                setTimeout(fetchDatasetSettings, 300);
            }
        });
    }

    const editKeywordsGroupsBtn = document.getElementById('edit-keywords-groups-btn');
    if (editKeywordsGroupsBtn) {
        editKeywordsGroupsBtn.addEventListener('click', function() {
            if (backend && typeof backend.openNativeKeywordGroupsDialog === 'function') {
                backend.openNativeKeywordGroupsDialog();
                setTimeout(fetchDatasetSettings, 300);
            }
        });
    }

    if (e621ToggleCb) {
        e621ToggleCb.addEventListener('change', function() {
            currentSettingsData.use_e621 = this.checked;
            if (backend) {
                backend.saveDatasetSettings(JSON.stringify(currentSettingsData));
            }
        });
    }

    if (tagInput) {
        tagInput.addEventListener('input', function() {
            const val = this.value.trim().toLowerCase();
            if (!val) {
                autoBox.style.display = 'none';
                return;
            }

            const useE621 = e621ToggleCb ? e621ToggleCb.checked : false;

            if (useE621 && backend && typeof backend.getE621AutocompleteSuggestions === 'function') {
                backend.getE621AutocompleteSuggestions(val, function(response) {
                    try {
                        const matches = JSON.parse(response);
                        renderAutocompleteItems(matches);
                    } catch (e) {
                        autoBox.style.display = 'none';
                    }
                });
            } else {
                fallbackLocalAutocomplete(val);
            }
        });

        tagInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                const val = this.value.trim().toLowerCase();
                if (val) {
                    addTagToSelection(val);
                    this.value = '';
                    autoBox.style.display = 'none';
                }
            } else if (e.key === 'Escape') {
                autoBox.style.display = 'none';
            }
        });
    }

    document.getElementById('open-dataset-btn').addEventListener('click', browseFolder);
    document.getElementById('settings-btn').addEventListener('click', openSettingsModal);
    document.getElementById('github-btn').addEventListener('click', () => {
        if (backend) backend.openExternalUrl('https://github.com/ViTa-Plane/taggui-next');
    });
    document.getElementById('help-btn').addEventListener('click', openHelpModal);

    document.getElementById('clear-filter-btn').addEventListener('click', clearFilter);
    document.getElementById('select-all-btn').addEventListener('click', selectAllFiltered);
    document.getElementById('clear-selection-btn').addEventListener('click', clearMultiSelection);

    document.getElementById('move-front-btn').addEventListener('click', moveKeywordsToFrontBtn);
    document.getElementById('apply-keywords-btn').addEventListener('click', applyKeywordsToSelectionBtn);
    document.getElementById('apply-all-keywords-btn').addEventListener('click', applyKeywordsToAll);
    document.getElementById('autotag-btn').addEventListener('click', triggerAutoTag);

    document.getElementById('sort-alpha-btn').addEventListener('click', () => sortActiveTags('alpha'));
    document.getElementById('sort-freq-btn').addEventListener('click', () => sortActiveTags('freq'));

    document.getElementById('close-help-x-btn').addEventListener('click', closeHelpModal);
    document.getElementById('close-help-btn').addEventListener('click', closeHelpModal);

    // document.getElementById('filter-input').addEventListener('input', onFilterInputChanged);
    document.getElementById('filter-input').addEventListener('input', debounce(onFilterInputChanged, 200));

    fetchDataset();
});


function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

function updateDatasetUI() {
    document.getElementById('total-count').innerText = datasetImages.length;
    document.getElementById('image-count').innerText = filteredImages.length;

    let rawPath = "";
    if (backend) {
        if (typeof backend.dataset_path_str === 'string') rawPath = backend.dataset_path_str;
        else if (typeof backend.dataset_path === 'string') rawPath = backend.dataset_path;
    }

    const pathLabelEl = document.getElementById('dataset-path-label');
    if (pathLabelEl) {
        pathLabelEl.style.cursor = 'pointer';
        pathLabelEl.title = "Click to open folder in system explorer";
        pathLabelEl.onclick = () => {
            if (backend && typeof backend.openDatasetInExplorer === 'function') backend.openDatasetInExplorer();
        };
    }

    if (rawPath) {
        const normalized = rawPath.replace(/\\/g, '/');
        const parts = normalized.split('/').filter(p => p.length > 0);
        pathLabelEl.innerText = parts.length > 0 ? parts.join('\\') : "\\";
        pathLabelEl.title = rawPath;
    } else {
        pathLabelEl.innerText = "No Dataset Loaded";
    }

    renderGlobalTagsList();
    renderGrid();
    if (filteredImages.length > 0 && selectedImageIndex === null) {
        selectImage(datasetImages.indexOf(filteredImages[0]), true);
    }
}

function onFilterInputChanged() {
    const input = document.getElementById('filter-input');
    const clearBtn = document.getElementById('clear-filter-btn');
    if (clearBtn) clearBtn.style.display = input.value.trim().length > 0 ? 'flex' : 'none';
    applyFilter();
}

function clearFilter() {
    const input = document.getElementById('filter-input');
    input.value = '';
    document.getElementById('clear-filter-btn').style.display = 'none';
    applyFilter();
    input.focus();
}

function applyFilter() {
    const query = document.getElementById('filter-input').value.trim().toLowerCase();
    if (!query) filteredImages = [...datasetImages];
    else if (query === 'untagged') filteredImages = datasetImages.filter(img => img.tags.length === 0);
    else {
        filteredImages = datasetImages.filter(img =>
            img.filename.toLowerCase().includes(query) ||
            img.tags.some(t => t.toLowerCase().includes(query))
        );
    }
    document.getElementById('image-count').innerText = filteredImages.length;
    document.getElementById('image-grid').innerHTML = '';
    renderGlobalTagsList();
    multiSelectedIndices.clear();
    if (filteredImages.length > 0) {
        selectImage(datasetImages.indexOf(filteredImages[0]), true);
    } else {
        selectedImageIndex = null;
        document.getElementById('selected-filename').innerText = "No image found";
        document.getElementById('active-tags-container').innerHTML = '';
        document.getElementById('active-tag-count').innerText = "Tags (0)";
    }
    renderGrid();
}

function renderGrid() {
    const grid = document.getElementById('image-grid');
    grid.innerHTML = '';

    filteredImages.forEach((img) => {
        const originalIdx = datasetImages.indexOf(img);
        const isSelected = selectedImageIndex === originalIdx;
        const isMultiSelected = multiSelectedIndices.has(originalIdx);
        const hasTags = img.tags.length > 0;

        const card = document.createElement('div');
        card.className = `image-card ${isSelected ? 'selected' : ''} ${isMultiSelected ? 'multi-selected' : ''}`;
        card.dataset.index = originalIdx;

        card.innerHTML = `
            <img src="${img.url}" loading="lazy" />
            <div class="badge-filename">${img.filename}</div>
            <div class="badge-tagged" style="display: ${hasTags ? 'block' : 'none'};">TAGGED</div>
            <div class="badge-delete" title="Delete image & tags">×</div>
        `;

        //  Bind right-click (contextmenu) on the image card to open the edit modal
        card.oncontextmenu = (e) => {
            e.preventDefault();
            e.stopPropagation();
            openBulkImageEditModal(originalIdx);
        };

        const imgElement = card.querySelector('img');
        imgElement.addEventListener('error', () => {
            imgElement.style.display = 'none';
        });

        const deleteBadge = card.querySelector('.badge-delete');
        deleteBadge.addEventListener('click', (e) => {
            promptDeleteImage(e, originalIdx);
        });

        card.onclick = (e) => {
            if (e.shiftKey && lastClickedIndex !== null) {
                const start = Math.min(lastClickedIndex, originalIdx);
                const end = Math.max(lastClickedIndex, originalIdx);
                for (let i = start; i <= end; i++) multiSelectedIndices.add(i);
            } else if (e.ctrlKey || e.metaKey) {
                if (multiSelectedIndices.has(originalIdx)) multiSelectedIndices.delete(originalIdx);
                else multiSelectedIndices.add(originalIdx);
            } else {
                multiSelectedIndices.clear();
                selectImage(originalIdx, true);
            }
            lastClickedIndex = originalIdx;
            updateGridSelectionUI();
        };
        grid.appendChild(card);
    });
    updateSelectionStatusText();
}

function openBulkImageEditModal(originalIdx) {
    const img = datasetImages[originalIdx];
    if (!img || !backend) return;

    const currentTagsStr = img.tags.join(', ');
    const modalTitle = `Edit Tag / Caption: ${img.filename}`;

    openEditTagModal(modalTitle, currentTagsStr, (newText) => {
        pushUndoState();

        const updatedTags = newText
            .replace(/\n/g, ',')
            .split(',')
            .map(t => t.trim())
            .filter(t => t.length > 0);

        img.tags = cleanImageTags(updatedTags);

        if (backend && typeof backend.saveImageTags === 'function') {
            backend.saveImageTags(img.relative_path, img.tags.join(', '));
        }

        renderActiveTags();
        renderGlobalTagsList();
        renderGrid();

        if (selectedImageIndex === originalIdx) {
            selectImage(originalIdx, true);
        }
    });
}

function promptDeleteImage(event, originalIdx) {
    event.stopPropagation();
    const img = datasetImages[originalIdx];
    if (!img || !backend) return;

    backend.confirmDeleteModal(img.filename, function(isConfirmed) {
        if (!isConfirmed) return;

        pushUndoState();
        backend.deleteImageAndTags(img.relative_path);
        datasetImages.splice(originalIdx, 1);
        applyFilter();
    });
}

function selectImage(idx, updateUI = true) {
    selectedImageIndex = idx;
    selectedActiveTagIndex = null;
    const img = datasetImages[idx];
    if (!img) return;
    document.getElementById('selected-filename').innerText = img.filename;
    renderActiveTags();
    if (updateUI) updateGridSelectionUI();
}

function updateGridSelectionUI() {
    const grid = document.getElementById('image-grid');
    Array.from(grid.children).forEach(card => {
        const idx = parseInt(card.dataset.index);
        card.classList.toggle('selected', idx === selectedImageIndex);
        card.classList.toggle('multi-selected', multiSelectedIndices.has(idx));
    });
    updateSelectionStatusText();
}

function updateSelectionStatusText() {
    const selectedCount = getSelectedIndices().length;
    document.getElementById('selection-counter').innerText = `${selectedCount} / ${filteredImages.length} selected`;
}

function clearMultiSelection() {
    multiSelectedIndices.clear();
    selectedImageIndex = null;
    selectedActiveTagIndex = null;
    document.getElementById('selected-filename').innerText = "No image selected";
    document.getElementById('active-tags-container').innerHTML = '';
    document.getElementById('active-tag-count').innerText = "Tags (0)";
    updateTokenDisplay("");
    updateGridSelectionUI();
}

function selectAllFiltered() {
    if (filteredImages.length === 0) return;
    multiSelectedIndices.clear();
    selectedImageIndex = datasetImages.indexOf(filteredImages[0]);
    for (let i = 1; i < filteredImages.length; i++) {
        multiSelectedIndices.add(datasetImages.indexOf(filteredImages[i]));
    }
    selectImage(selectedImageIndex, false);
    updateGridSelectionUI();
}

function deleteTagGlobally(tagToDelete) {
    if (!tagToDelete) return;
    pushUndoState();
    const updates = {};
    datasetImages.forEach(img => {
        const initialLen = img.tags.length;
        img.tags = img.tags.filter(t => t.toLowerCase() !== tagToDelete.toLowerCase());
        if (img.tags.length !== initialLen) {
            updates[img.relative_path] = img.tags.join(', ');
        }
    });
    if (backend && Object.keys(updates).length > 0) {
        backend.saveBatchImageTags(JSON.stringify(updates));
    }
    selectedLeftTag = null;
    renderGlobalTagsList();
    renderActiveTags();
    renderGrid();
}

// ==========================================
// --- SECTION: LEFT PANEL (GLOBAL TAGS)
// ==========================================
function renderGlobalTagsList() {
    const container = document.getElementById('global-tags-list');
    if (!container) return;
    container.innerHTML = '';

    container.oncontextmenu = (e) => {
        e.preventDefault();
        if (selectedLeftTag) {
            const tagToEdit = selectedLeftTag;
            openEditTagModal("Edit Tag / Caption:", tagToEdit, (newTagVal) => {
                const trimmedNew = newTagVal.trim().toLowerCase();
                if (!trimmedNew || trimmedNew === tagToEdit.toLowerCase()) return;

                pushUndoState();
                const updates = {};
                datasetImages.forEach(img => {
                    let changed = false;
                    img.tags = img.tags.map(t => {
                        if (t.toLowerCase() === tagToEdit.toLowerCase()) {
                            changed = true;
                            return trimmedNew;
                        }
                        return t;
                    });
                    if (changed) {
                        img.tags = cleanImageTags(img.tags);
                        updates[img.relative_path] = img.tags.join(', ');
                    }
                });

                if (backend && Object.keys(updates).length > 0) {
                    backend.saveBatchImageTags(JSON.stringify(updates));
                }
                selectedLeftTag = trimmedNew;
                renderGlobalTagsList();
                renderActiveTags();
                renderGrid();
            });
        }
    };

    const currentQuery = document.getElementById('filter-input').value.trim().toLowerCase();
    const activeKeywords = keywordsCombo ? keywordsCombo.value.split(',').map(k => k.trim().toLowerCase()).filter(k => k.length > 0) : [];

    const tagCounts = {};
    datasetImages.forEach(img => img.tags.forEach(t => tagCounts[t] = (tagCounts[t] || 0) + 1));
    const sortedTags = Object.entries(tagCounts).sort((a,b) => b[1] - a[1]);
    let firstMatchNode = null;

    sortedTags.forEach(([tag, count]) => {
        const isHighlighted = currentQuery && tag.toLowerCase().includes(currentQuery);
        const isKeyword = activeKeywords.includes(tag.toLowerCase());
        const isSelected = selectedLeftTag && selectedLeftTag.toLowerCase() === tag.toLowerCase();

        const item = document.createElement('div');
        item.title = "Click: Select/Highlight | Right-click: Edit tag | Delete: Remove from all images | Ctrl+Click: Add Keyword | Shift+Click: Add to Selection";
        item.style.cssText = `
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            font-family: monospace;
            padding: 4px 6px;
            cursor: pointer;
            border-radius: 4px;
            color: ${isSelected ? '#ffffff' : (isHighlighted ? '#ffffff' : '#cbd5e1')};
            background: ${isSelected ? 'rgba(56, 189, 248, 0.3)' : (isHighlighted ? 'rgba(99, 102, 241, 0.25)' : 'transparent')};
            border-left: ${isSelected ? '2px solid #38bdf8' : (isKeyword ? '2px solid #10b981' : (isHighlighted ? '2px solid #6366f1' : 'none'))};
        `;
        item.innerHTML = `<span>${tag}</span> <span style="color: #64748b;">${count}</span>`;

        item.onclick = (e) => {
            if ((e.ctrlKey || e.metaKey)) {
                if (isKeyword) {
                    removeFromKeywords(tag);
                } else {
                    addToKeywords(tag);
                }
                e.stopPropagation();
            } else if (e.shiftKey && e.altKey) {
                pushUndoState();
                const targets = getSelectedIndices();
                const updates = {};
                targets.forEach(idx => {
                    const img = datasetImages[idx];
                    img.tags = img.tags.filter(t => t.toLowerCase() !== tag.toLowerCase());
                    updates[img.relative_path] = img.tags.join(', ');
                });
                if (backend && targets.length > 0) backend.saveBatchImageTags(JSON.stringify(updates));
                renderActiveTags();
                renderGlobalTagsList();
                renderGrid();
                e.stopPropagation();
            } else if (e.shiftKey) {
                pushUndoState();
                const targets = getSelectedIndices();
                const updates = {};

                const allHaveTag = targets.length > 0 && targets.every(idx => {
                    return datasetImages[idx].tags.map(t => t.toLowerCase()).includes(tag.toLowerCase());
                });

                targets.forEach(idx => {
                    const img = datasetImages[idx];
                    if (allHaveTag) {
                        img.tags = img.tags.filter(t => t.toLowerCase() !== tag.toLowerCase());
                    } else {
                        addTagToImage(img, tag);
                    }
                    updates[img.relative_path] = img.tags.join(', ');
                });

                if (backend && targets.length > 0) backend.saveBatchImageTags(JSON.stringify(updates));
                renderActiveTags();
                renderGlobalTagsList();
                renderGrid();
                e.stopPropagation();
            } else {
                selectedLeftTag = tag;
                document.getElementById('filter-input').value = tag;
                onFilterInputChanged();
                renderGlobalTagsList();
            }
        };

        container.appendChild(item);
        if (isHighlighted && !firstMatchNode) firstMatchNode = item;
    });

    if (firstMatchNode) {
        firstMatchNode.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

// ==========================================
// --- SECTION: RIGHT PANEL (ACTIVE TAGS)
// ==========================================
function renderActiveTags() {
    if (selectedImageIndex === null) return;
    const img = datasetImages[selectedImageIndex];
    const container = document.getElementById('active-tags-container');
    if (!container) return;
    container.innerHTML = '';

    document.getElementById('active-tag-count').innerText = `Tags (${img.tags.length})`;
    const currentQuery = document.getElementById('filter-input').value.trim().toLowerCase();
    const activeKeywords = keywordsCombo ? keywordsCombo.value.split(',').map(k => k.trim().toLowerCase()).filter(k => k.length > 0) : [];

    let dropIndicator = document.getElementById('tag-drop-indicator');
    if (!dropIndicator) {
        dropIndicator = document.createElement('div');
        dropIndicator.id = 'tag-drop-indicator';
        dropIndicator.style.cssText = `width: 3px; background-color: #38bdf8; box-shadow: 0 0 8px #38bdf8; border-radius: 2px; margin: 0 2px; pointer-events: none; display: none; z-index: 10;`;
    }

    let targetDropIdx = null;

    container.ondragover = (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';

        const chips = Array.from(container.querySelectorAll('.tag-chip'));
        if (chips.length === 0) return;

        let closestChip = null;
        let closestDistance = Infinity;
        let insertBefore = true;

        chips.forEach(chip => {
            const rect = chip.getBoundingClientRect();
            const midX = rect.left + rect.width / 2;
            const midY = rect.top + rect.height / 2;
            const dist = Math.hypot(e.clientX - midX, e.clientY - midY);
            if (dist < closestDistance) {
                closestDistance = dist;
                closestChip = chip;
                insertBefore = e.clientX < midX;
            }
        });

        if (closestChip) {
            dropIndicator.style.display = 'inline-block';
            dropIndicator.style.height = `${closestChip.offsetHeight || 22}px`;
            const idx = parseInt(closestChip.dataset.index);
            if (insertBefore) {
                container.insertBefore(dropIndicator, closestChip);
                targetDropIdx = idx;
            } else {
                container.insertBefore(dropIndicator, closestChip.nextSibling);
                targetDropIdx = idx + 1;
            }
        }
    };

    container.ondragenter = (e) => {
        e.preventDefault();
    };

    container.ondrop = (e) => {
        e.preventDefault();
        const fromIdxStr = e.dataTransfer.getData('text/plain');
        if (fromIdxStr === "" || fromIdxStr === null || fromIdxStr === undefined) return;
        const fromIdx = parseInt(fromIdxStr);
        let toIdx = targetDropIdx;

        if (dropIndicator.parentNode) dropIndicator.parentNode.removeChild(dropIndicator);
        dropIndicator.style.display = 'none';

        if (toIdx === null || isNaN(fromIdx)) return;

        if (fromIdx < toIdx) toIdx--;
        if (fromIdx === toIdx) return;

        pushUndoState();
        const movedTag = img.tags.splice(fromIdx, 1)[0];
        img.tags.splice(toIdx, 0, movedTag);

        if (selectedActiveTagIndex === fromIdx) {
            selectedActiveTagIndex = toIdx;
        } else if (selectedActiveTagIndex > fromIdx && selectedActiveTagIndex <= toIdx) {
            selectedActiveTagIndex--;
        } else if (selectedActiveTagIndex < fromIdx && selectedActiveTagIndex >= toIdx) {
            selectedActiveTagIndex++;
        }

        if (backend) backend.saveImageTags(img.relative_path, img.tags.join(', '));
        renderActiveTags();
        renderGlobalTagsList();
        renderGrid();
    };

    const editActiveTag = (tagIdx) => {
        const tagToEdit = img.tags[tagIdx];
        if (!tagToEdit) return;
        openEditTagModal("Edit Tag / Caption:", tagToEdit, (newTagVal) => {
            const trimmedNew = newTagVal.trim();
            if (!trimmedNew || trimmedNew.toLowerCase() === tagToEdit.toLowerCase()) return;

            pushUndoState();
            img.tags[tagIdx] = trimmedNew;
            img.tags = cleanImageTags(img.tags);
            if (backend) backend.saveImageTags(img.relative_path, img.tags.join(', '));
            renderActiveTags();
            renderGlobalTagsList();
            renderGrid();
        });
    };

    container.oncontextmenu = (e) => {
        e.preventDefault();
        if (selectedActiveTagIndex !== null && img.tags[selectedActiveTagIndex]) {
            editActiveTag(selectedActiveTagIndex);
        }
    };

    img.tags.forEach((tag, tagIdx) => {
        const isKeyword = activeKeywords.includes(tag.toLowerCase());
        const isSearchMatch = currentQuery && tag.toLowerCase().includes(currentQuery);
        const isTagSelected = selectedActiveTagIndex === tagIdx;

        const chip = document.createElement('span');
        chip.className = `tag-chip ${isTagSelected ? 'selected' : ''}`;
        chip.draggable = true;
        chip.dataset.index = tagIdx;
        chip.title = "Right-click: Edit tag | Click: Select/Highlight | Arrow keys: Move position | Drag to reorder";

        if (isTagSelected) {
            chip.style.borderColor = '';
            chip.style.backgroundColor = '';
            chip.style.color = '';
        } else if (isKeyword) {
            chip.style.borderColor = '#10b981';
            chip.style.backgroundColor = 'rgba(16, 185, 129, 0.25)';
            chip.style.color = '#34d399';
        } else if (isSearchMatch) {
            chip.style.borderColor = '#38bdf8';
            chip.style.backgroundColor = 'rgba(56, 189, 248, 0.25)';
            chip.style.color = '#ffffff';
        }

        chip.innerHTML = `${tag} <span title="Remove tag">×</span>`;

        chip.oncontextmenu = (e) => {
            e.preventDefault();
            e.stopPropagation();
            selectedActiveTagIndex = tagIdx;
            renderActiveTags();
            editActiveTag(tagIdx);
        };

        chip.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('text/plain', tagIdx.toString());
            e.dataTransfer.effectAllowed = 'move';
            setTimeout(() => { chip.style.opacity = '0.3'; }, 0);
        });

        chip.addEventListener('dragend', () => {
            chip.style.opacity = '1';
            if (dropIndicator.parentNode) dropIndicator.parentNode.removeChild(dropIndicator);
            dropIndicator.style.display = 'none';
        });

        chip.onclick = (e) => {
            if ((e.ctrlKey || e.metaKey)) {
                if (isKeyword) {
                    removeFromKeywords(tag);
                } else {
                    addToKeywords(tag);
                }
            } else if (e.shiftKey) {
                pushUndoState();
                if (img.tags.map(t => t.toLowerCase()).includes(tag.toLowerCase())) {
                    img.tags = img.tags.filter(t => t.toLowerCase() !== tag.toLowerCase());
                } else {
                    addTagToImage(img, tag);
                }
                if (backend) backend.saveImageTags(img.relative_path, img.tags.join(', '));
                renderActiveTags();
                renderGlobalTagsList();
                renderGrid();
            } else {
                // --- Toggle selection: click to select, second click to deselect ---
                if (selectedActiveTagIndex === tagIdx) {
                    selectedActiveTagIndex = null;
                } else {
                    selectedActiveTagIndex = tagIdx;
                }
                renderActiveTags();
            }
            e.stopPropagation();
        };

        chip.querySelector('span').onclick = (e) => {
            e.stopPropagation();
            pushUndoState();
            img.tags = img.tags.filter(t => t !== tag);
            if (selectedActiveTagIndex === tagIdx) selectedActiveTagIndex = null;
            else if (selectedActiveTagIndex > tagIdx) selectedActiveTagIndex--;
            if (backend) backend.saveImageTags(img.relative_path, img.tags.join(', '));
            renderActiveTags();
            renderGlobalTagsList();
            renderGrid();
        };

        container.appendChild(chip);
    });

    updateTokenDisplay(img.tags.join(', '));
}

function sortActiveTags(method) {
    if (selectedImageIndex === null) return;
    const img = datasetImages[selectedImageIndex];
    if (!img || img.tags.length <= 1) return;

    pushUndoState();
    const activeKeywords = keywordsCombo ? keywordsCombo.value.split(',').map(k => k.trim().toLowerCase()).filter(k => k.length > 0) : [];
    const keywordTags = [];
    const standardTags = [];

    img.tags.forEach(tag => {
        if (activeKeywords.includes(tag.toLowerCase())) keywordTags.push(tag);
        else standardTags.push(tag);
    });

    if (method === 'alpha') {
        standardTags.sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'accent' }));
    } else if (method === 'freq') {
        const globalCounts = {};
        datasetImages.forEach(dImg => dImg.tags.forEach(t => globalCounts[t.toLowerCase()] = (globalCounts[t.toLowerCase()] || 0) + 1));
        standardTags.sort((a, b) => (globalCounts[b.toLowerCase()] || 0) - (globalCounts[a.toLowerCase()] || 0) || a.localeCompare(b));
    }

    img.tags = [...keywordTags, ...standardTags];
    if (backend) backend.saveImageTags(img.relative_path, img.tags.join(', '));
    renderActiveTags();
    renderGlobalTagsList();
    renderGrid();
}

function addTagToSelection(newTag) {
    if (!newTag || selectedImageIndex === null) return;
    pushUndoState();
    const targets = getSelectedIndices();
    const updates = {};
    targets.forEach(idx => {
        const img = datasetImages[idx];
        addTagToImage(img, newTag);
        updates[img.relative_path] = img.tags.join(', ');
    });
    if (backend) backend.saveBatchImageTags(JSON.stringify(updates));
    renderActiveTags();
    renderGlobalTagsList();
    renderGrid();
}

function addToKeywords(tag) {
    if (!keywordsCombo) return;
    pushUndoState();
    const currentVal = keywordsCombo.value.trim();
    let keywordsList = currentVal ? currentVal.split(',').map(k => k.trim()).filter(k => k.length > 0) : [];

    if (!keywordsList.map(k => k.toLowerCase()).includes(tag.toLowerCase())) {
        keywordsList.push(tag);
        const newVal = keywordsList.join(', ');

        let foundMatch = false;
        for (let i = 0; i < keywordsCombo.options.length; i++) {
            if (keywordsCombo.options[i].value === currentVal || keywordsCombo.selectedIndex === i) {
                keywordsCombo.options[i].value = newVal;
                const fullText = keywordsCombo.options[i].text;
                const groupTitle = fullText.includes(':') ? fullText.split(':')[0].trim() : "General";
                keywordsCombo.options[i].text = `${groupTitle}: ${newVal}`;
                keywordsCombo.selectedIndex = i;

                if (currentSettingsData.keyword_groups) {
                    const groupKey = groupTitle.toLowerCase();
                    if (currentSettingsData.keyword_groups[groupKey]) {
                        currentSettingsData.keyword_groups[groupKey] = [...keywordsList];
                    }
                }
                foundMatch = true;
                break;
            }
        }

        if (!foundMatch) {
            const opt = document.createElement('option');
            opt.value = newVal;
            opt.text = `Custom: ${newVal}`;
            keywordsCombo.appendChild(opt);
            keywordsCombo.value = newVal;
        }

        renderActiveTags();
        renderGlobalTagsList();

        if (backend) {
            currentSettingsData.keywords = keywordsCombo.value;
            backend.saveDatasetSettings(JSON.stringify(currentSettingsData));
        }
    }
}

function removeFromKeywords(tag) {
    if (!keywordsCombo) return;
    const currentVal = keywordsCombo.value.trim();
    if (!currentVal) return;
    pushUndoState();

    let keywordsList = currentVal.split(',').map(k => k.trim()).filter(k => k.length > 0);
    const updatedList = keywordsList.filter(k => k.toLowerCase() !== tag.toLowerCase());

    if (updatedList.length !== keywordsList.length) {
        const newVal = updatedList.join(', ');
        for (let i = 0; i < keywordsCombo.options.length; i++) {
            if (keywordsCombo.options[i].value === currentVal || keywordsCombo.selectedIndex === i) {
                keywordsCombo.options[i].value = newVal;
                const groupTitle = keywordsCombo.options[i].text.split(':')[0];
                keywordsCombo.options[i].text = `${groupTitle}: ${newVal}`;
                keywordsCombo.selectedIndex = i;

                if (currentSettingsData.keyword_groups) {
                    const groupKey = groupTitle.toLowerCase();
                    if (currentSettingsData.keyword_groups[groupKey]) {
                        currentSettingsData.keyword_groups[groupKey] = [...updatedList];
                    }
                }
                break;
            }
        }

        renderActiveTags();
        renderGlobalTagsList();

        if (backend) {
            currentSettingsData.keywords = keywordsCombo.value;
            backend.saveDatasetSettings(JSON.stringify(currentSettingsData));
        }
    }
}

function moveKeywordsToFrontBtn() {
    if (!keywordsCombo) return;
    const val = keywordsCombo.value.trim();
    if (val && selectedImageIndex !== null) {
        moveKeywordsToFrontForSelection(val);
    } else {
        alert("Please select an image and pick a keyword group first.");
    }
}

function moveKeywordsToFrontForSelection(keywordsStr) {
    if (!keywordsStr) return;
    const rawKeywords = keywordsStr.split(',').map(k => k.trim().toLowerCase()).filter(k => k.length > 0);
    if (rawKeywords.length === 0) return;

    pushUndoState();
    const targets = getSelectedIndices();
    const updates = {};

    targets.forEach(idx => {
        const img = datasetImages[idx];
        const imgTagsLower = img.tags.map(t => t.toLowerCase());
        const presentKeywords = rawKeywords.filter(kw => imgTagsLower.includes(kw));

        if (presentKeywords.length > 0) {
            const remainingTags = img.tags.filter(t => !presentKeywords.includes(t.toLowerCase()));
            img.tags = cleanImageTags([...presentKeywords, ...remainingTags]);
            updates[img.relative_path] = img.tags.join(', ');
        }
    });

    if (backend && Object.keys(updates).length > 0) {
        backend.saveBatchImageTags(JSON.stringify(updates));
    }

    renderActiveTags();
    renderGlobalTagsList();
    renderGrid();
}

function updateTokenDisplay(tagsString) {
    if (!backend) return;
    backend.estimateTokens(tagsString, function(count) {
        document.getElementById('token-label').innerText = `${count} / 75`;
        const pct = Math.min((count / 75) * 100, 100);
        const bar = document.getElementById('token-progress');
        bar.style.width = `${pct}%`;
        bar.style.backgroundColor = count > 75 ? '#ef4444' : '#6366f1';
    });
}

function applyKeywordsToSelectionBtn() {
    if (!keywordsCombo) return;
    const val = keywordsCombo.value.trim();
    if (val && selectedImageIndex !== null) applyKeywordsToSelection(val);
}

function applyKeywordsToSelection(keywordsStr) {
    if (!keywordsStr || selectedImageIndex === null) return;
    const rawKeywords = keywordsStr.split(',').map(k => k.trim().toLowerCase()).filter(k => k.length > 0);
    if (rawKeywords.length === 0) return;

    pushUndoState();
    const targets = getSelectedIndices();
    const updates = {};
    targets.forEach(idx => {
        const img = datasetImages[idx];
        const remainingTags = img.tags.filter(t => !rawKeywords.includes(t.toLowerCase()));
        img.tags = [...rawKeywords, ...remainingTags];
        updates[img.relative_path] = img.tags.join(', ');
    });
    if (backend) backend.saveBatchImageTags(JSON.stringify(updates));
    renderActiveTags();
    renderGlobalTagsList();
    renderGrid();
}

function applyKeywordsToAll() {
    if (!keywordsCombo) return;
    const keywordsStr = keywordsCombo.value.trim();
    const rawKeywords = keywordsStr.split(',').map(k => k.trim().toLowerCase()).filter(k => k.length > 0);
    if (rawKeywords.length === 0 || datasetImages.length === 0) return;

    pushUndoState();
    const updates = {};
    datasetImages.forEach(img => {
        const remainingTags = img.tags.filter(t => !rawKeywords.includes(t.toLowerCase()));
        img.tags = [...rawKeywords, ...remainingTags];
        updates[img.relative_path] = img.tags.join(', ');
    });
    if (backend) backend.saveBatchImageTags(JSON.stringify(updates));
    renderActiveTags();
    renderGlobalTagsList();
    renderGrid();
}

function triggerAutoTag() {
    if (selectedImageIndex === null) {
        // Call Python backend to show the custom styled warning dialog
        if (typeof backend !== 'undefined' && backend.showWarningDialog) {
            backend.showWarningDialog("Selection Warning", "Please select an image first.");
        } else {
            alert("Please select an image first."); // Fallback if bridge isn't loaded yet
        }
        return;
    }

    const targets = getSelectedIndices();
    if (targets.length === 0) return;

    backend.confirmAutoTagModal(targets.length, function(isConfirmed) {
        if (!isConfirmed) return;

        pushUndoState();
        const pathsToProcess = targets.map(idx => datasetImages[idx].relative_path).filter(p => p);
        if (pathsToProcess.length === 0) return;

        if (backend && typeof backend.autoTagBatch === 'function') {
            backend.autoTagBatch(JSON.stringify(pathsToProcess), function(resultsJson) {
                try {
                    const results = JSON.parse(resultsJson);

                    targets.forEach(idx => {
                        const img = datasetImages[idx];
                        if (img && results[img.relative_path]) {
                            const returnedTagsStr = results[img.relative_path];
                            img.tags = cleanImageTags(
                                returnedTagsStr.split(',').map(t => t.trim()).filter(t => t.length > 0)
                            );
                        }
                    });

                    const batchUpdates = {};
                    targets.forEach(idx => {
                        const img = datasetImages[idx];
                        if (img) batchUpdates[img.relative_path] = img.tags.join(', ');
                    });
                    if (Object.keys(batchUpdates).length > 0) {
                        backend.saveBatchImageTags(JSON.stringify(batchUpdates));
                    }

                    renderActiveTags();
                    renderGlobalTagsList();
                    renderGrid();
                } catch(e) {
                    console.error("Batch tag processing response error:", e);
                }
            });
        }
    });
}

// ==========================================
// --- SECTION: Autocomplete & Global Listeners
// ==========================================

function renderAutocompleteItems(matches) {
    if (!autoBox) return;
    autoBox.innerHTML = '';
    if (!matches || matches.length === 0) {
        autoBox.style.display = 'none';
        return;
    }
    matches.forEach(match => {
        const div = document.createElement('div');
        div.className = 'autocomplete-item';
        div.innerText = match;
        div.onclick = () => {
            addTagToSelection(match);
            tagInput.value = '';
            autoBox.style.display = 'none';
            tagInput.focus();
        };
        autoBox.appendChild(div);
    });
    autoBox.style.display = 'block';
}

function fallbackLocalAutocomplete(val) {
    const allTags = new Set();
    datasetImages.forEach(img => img.tags.forEach(t => allTags.add(t)));
    const matches = Array.from(allTags).filter(t => t.toLowerCase().includes(val) && t.toLowerCase() !== val).slice(0, 6);
    renderAutocompleteItems(matches);
}

// Disable default Chromium right-click context menu globally
document.addEventListener('contextmenu', function(e) {
    e.preventDefault();
}, false);

document.addEventListener('keydown', function(e) {
    const activeInput = document.activeElement === tagInput || document.activeElement === document.getElementById('filter-input') || document.activeElement === keywordsCombo;

    if (selectedActiveTagIndex !== null && !activeInput && selectedImageIndex !== null) {
        const img = datasetImages[selectedImageIndex];
        if (img && img.tags.length > 1) {
            let step = 1;
            let isBackward = false;

            if (e.key === 'ArrowLeft') {
                step = 1;
                isBackward = true;
            } else if (e.key === 'ArrowRight') {
                step = 1;
                isBackward = false;
            } else if (e.key === 'ArrowUp') {
                step = 2;
                isBackward = true;
            } else if (e.key === 'ArrowDown') {
                step = 2;
                isBackward = false;
            } else if (e.key === 'Escape') {
                selectedActiveTagIndex = null;
                renderActiveTags();
                e.preventDefault();
                return;
            } else {
                return;
            }

            e.preventDefault();

            let targetIndex = isBackward ? selectedActiveTagIndex - step : selectedActiveTagIndex + step;
            targetIndex = Math.max(0, Math.min(img.tags.length - 1, targetIndex));

            if (targetIndex !== selectedActiveTagIndex) {
                pushUndoState();
                const movedTag = img.tags.splice(selectedActiveTagIndex, 1)[0];
                img.tags.splice(targetIndex, 0, movedTag);
                selectedActiveTagIndex = targetIndex;

                if (backend) backend.saveImageTags(img.relative_path, img.tags.join(', '));
                renderActiveTags();
                renderGlobalTagsList();
                renderGrid();
            }
            return;
        }
    }

    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'd' && !activeInput) {
        e.preventDefault();
        multiSelectedIndices.clear();
        selectedImageIndex = null;
        selectedActiveTagIndex = null;
        document.getElementById('selected-filename').innerText = "No image selected";
        document.getElementById('active-tags-container').innerHTML = '';
        document.getElementById('active-tag-count').innerText = "Tags (0)";
        updateTokenDisplay("");
        updateGridSelectionUI();
        return;
    }

    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        performRedo();
        return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault();
        performUndo();
        return;
    }
    if ((e.key === 'Delete' || e.key === 'Backspace') && !activeInput && selectedLeftTag) {
        e.preventDefault();
        deleteTagGlobally(selectedLeftTag);
        return;
    }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a' && !activeInput) {
        e.preventDefault();
        selectAllFiltered();
        return;
    }
    if (e.key === 'Escape') {
        document.activeElement.blur();
        selectedLeftTag = null;
        selectedActiveTagIndex = null;
        renderGlobalTagsList();
        renderActiveTags();
        if (autoBox) autoBox.style.display = 'none';
        clearMultiSelection();
        return;
    }

    if (activeInput || filteredImages.length === 0) return;

    let currentFilteredIdx = filteredImages.findIndex(img => datasetImages.indexOf(img) === selectedImageIndex);
    if (currentFilteredIdx === -1) currentFilteredIdx = 0;

    const gridEl = document.getElementById('image-grid');
    const cols = Math.max(1, Math.floor(gridEl.clientWidth / 216));
    let nextFilteredIdx = currentFilteredIdx;

    if (e.key === 'ArrowRight') nextFilteredIdx = Math.min(filteredImages.length - 1, currentFilteredIdx + 1);
    else if (e.key === 'ArrowLeft') nextFilteredIdx = Math.max(0, currentFilteredIdx - 1);
    else if (e.key === 'ArrowDown') nextFilteredIdx = Math.min(filteredImages.length - 1, currentFilteredIdx + cols);
    else if (e.key === 'ArrowUp') nextFilteredIdx = Math.max(0, currentFilteredIdx - cols);
    else if (e.key === 'Enter') {
        if (tagInput) tagInput.focus();
        e.preventDefault();
        return;
    }

    if (nextFilteredIdx !== currentFilteredIdx) {
        e.preventDefault();
        selectImage(datasetImages.indexOf(filteredImages[nextFilteredIdx]), true);
        const cardNode = gridEl.children[nextFilteredIdx];
        if (cardNode) cardNode.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
});