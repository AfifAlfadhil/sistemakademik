document.addEventListener('DOMContentLoaded', () => {
    // Check Auth
    if (localStorage.getItem('userRole') !== 'admin') {
        window.location.href = 'index.html';
        return;
    }

    document.getElementById('admin-logout-btn').addEventListener('click', () => {
        localStorage.removeItem('userRole');
        window.location.href = 'index.html';
    });

    const dragDropArea = document.getElementById('drag-drop-area');
    const fileInput = document.getElementById('file-input');
    const progressCompact = document.getElementById('progress-compact');
    const progressFill = document.getElementById('progress-fill');
    const uploadStatusText = document.getElementById('upload-status-text');
    const documentTableBody = document.getElementById('document-table-body');

    let documents = [];

    function renderTable() {
        documentTableBody.innerHTML = '';
        documents.forEach(doc => {
            const tr = document.createElement('tr');
            
            let statusHtml = doc.status === 'Ready' 
                ? `<span class="badge ready"><i class="ph-bold ph-check"></i> Selesai</span>`
                : `<span class="badge proc"><i class="ph-bold ph-spinner-gap" style="animation: spin 1s linear infinite;"></i> Proses</span>`;

            tr.innerHTML = `
                <td><i class="ph-fill ph-file-pdf" style="margin-right:8px; color:var(--text-muted); font-size:18px; vertical-align:middle;"></i> ${escapeHTML(doc.file)}</td>
                <td>${escapeHTML(doc.date)}</td>
                <td>${statusHtml}</td>
            `;
            documentTableBody.appendChild(tr);
        });
    }

    async function loadDocuments() {
        try {
            // Tambahkan timestamp untuk menghindari browser caching
            const res = await fetch('/api/documents?t=' + new Date().getTime());
            if (res.ok) {
                const data = await res.json();
                documents = data.documents;
                renderTable();
            }
        } catch (e) {
            console.error('Gagal memuat dokumen', e);
        }
    }

    function escapeHTML(str) {
        return str.replace(/[&<>'"]/g,
            tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
        );
    }

    loadDocuments();

    // --- Upload Logic ---
    dragDropArea.addEventListener('click', () => fileInput.click());
    
    dragDropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        dragDropArea.style.background = '#F0F0F0';
    });
    
    dragDropArea.addEventListener('dragleave', () => {
        dragDropArea.style.background = '#FFF';
    });

    dragDropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dragDropArea.style.background = '#FFF';
        if (e.dataTransfer.files.length > 0) {
            handleFileUpload(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    async function handleFileUpload(file) {
        if (file.type !== 'application/pdf') {
            alert('Mohon unggah file PDF.');
            return;
        }

        dragDropArea.classList.add('hidden');
        progressCompact.classList.remove('hidden');
        uploadStatusText.textContent = `Mengunggah...`;
        progressFill.style.width = '0%';
        progressFill.style.background = 'var(--accent-primary)';
        
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            const res = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });
            
            if (!res.ok) {
                throw new Error('Gagal mengunggah file.');
            }
            
            progressFill.style.width = '100%';
            uploadStatusText.textContent = `Selesai!`;
            
            await loadDocuments();
            
            setTimeout(() => {
                progressCompact.classList.add('hidden');
                dragDropArea.classList.remove('hidden');
                fileInput.value = '';
            }, 800);
        } catch (e) {
            alert('Error: ' + e.message);
            progressCompact.classList.add('hidden');
            dragDropArea.classList.remove('hidden');
        }
    }
});
