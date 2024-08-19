async function fetchDirectoryStructure() {
    try {
        const treeData = buildTreeData( await eel.py_get_dir_structure()() );
        displayDirectoryStructure(treeData);
    } catch (error) {
        console.error('Error fetching directory structure:', error);
    }
}

function buildTreeData(paths) {
    const tree = {};
    paths.forEach(path => {
        const parts = path.split('\\')
        // parts.splice(0,1);
        let current = tree;
        parts.forEach((part, index) => {
            if (!current[part]) {
                current[part] = index === parts.length - 1 ? null : {};
            }
            current = current[part];
        });
    });
    return tree;
}

function displayDirectoryStructure(treeData) {
    const directoryList = document.getElementById('directoryList');
    directoryList.innerHTML = ''; // Clear previous directory list

    const tree = buildTree(treeData);
    directoryList.appendChild(tree);
}

function buildTree(treeData, parentPath = '') {
    const ul = document.createElement('ul');
    Object.keys(treeData).forEach(key => {
        const li = document.createElement('li');
        const fullPath = parentPath ? `${parentPath}/${key}` : key;
        li.textContent = key;
        li.className = 'collapsed unselected';
        li.onclick = (event) => {
            event.stopPropagation();
            toggleExpandCollapse(li);
            handleDirectorySelection(li, fullPath);
        };
        if (treeData[key] !== null) {
            const childUl = buildTree(treeData[key], fullPath);
            li.appendChild(childUl);
        }
        ul.appendChild(li);
    });
    if (!parentPath) {
        ul.firstChild.click(); // select the first element
    }
    return ul;
}

function toggleExpandCollapse(li) {
    li.classList.toggle('collapsed');
    li.classList.toggle('expanded');
}

function handleDirectorySelection(li, fullPath) {
    // Remove 'selected' class from all li elements
    const allLi = document.querySelectorAll('li');
    
    allLi.forEach(item => {
        item.classList.remove('selected');
        item.classList.add('unselected');
    });

    li.classList.remove('unselected');
    li.classList.add('selected');


    console.log('Selected directory:', fullPath);
    window.opener.postMessage({ type: 'selected-directory', fullPath: fullPath }, '*');
}

fetchDirectoryStructure();
