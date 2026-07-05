document.addEventListener('DOMContentLoaded', () => {
    // Check Auth
    if (localStorage.getItem('userRole') !== 'admin') {
        window.location.href = 'index.html';
        return;
    }

    document.getElementById('admin-logout-btn').addEventListener('click', () => {
        localStorage.removeItem('userRole');
        localStorage.removeItem('username');
        window.location.href = 'index.html';
    });

    const dragDropArea = document.getElementById('drag-drop-area');
    const fileInput = document.getElementById('file-input');
    const progressCompact = document.getElementById('progress-compact');
    const progressFill = document.getElementById('progress-fill');
    const uploadStatusText = document.getElementById('upload-status-text');
    const documentTableBody = document.getElementById('document-table-body');
    const terminalMonitor = document.getElementById('terminal-monitor');
    const terminalFilename = document.getElementById('terminal-filename');
    const terminalLogsContent = document.getElementById('terminal-logs-content');

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

    let logInterval = null;

    function startLogPolling(filename) {
        if (logInterval) clearInterval(logInterval);
        
        terminalMonitor.classList.remove('hidden');
        terminalFilename.textContent = filename;
        terminalLogsContent.innerHTML = '<div style="color: #6B7280;">Menghubungkan ke log stream...</div>';
        
        logInterval = setInterval(async () => {
            try {
                const res = await fetch(`/api/upload/logs/${encodeURIComponent(filename)}?t=${Date.now()}`);
                if (res.ok) {
                    const data = await res.json();
                    
                    let formattedLogs = '';
                    let completed = false;
                    
                    data.logs.forEach(line => {
                        let colorStyle = '';
                        if (line.includes('SUCCESS:')) {
                            colorStyle = 'color: #10B981; font-weight: 600;'; // Green
                            completed = true;
                        } else if (line.includes('CRITICAL ERROR') || line.includes('ERROR:')) {
                            colorStyle = 'color: #EF4444; font-weight: 600;'; // Red
                            completed = true;
                        } else if (line.includes('Peringatan:')) {
                            colorStyle = 'color: #F59E0B;'; // Amber
                        } else if (line.includes('Memulai') || line.includes('Sukses membuat')) {
                            colorStyle = 'color: #38BDF8;'; // Light Blue
                        }
                        
                        formattedLogs += `<div style="margin-bottom: 4px; ${colorStyle}">${escapeHTML(line)}</div>`;
                    });
                    
                    terminalLogsContent.innerHTML = formattedLogs;
                    
                    // Auto scroll to bottom
                    terminalMonitor.scrollTop = terminalMonitor.scrollHeight;
                    
                    if (completed) {
                        clearInterval(logInterval);
                        logInterval = null;
                        
                        await loadDocuments();
                        
                        // Close logs panel after 5 seconds
                        setTimeout(() => {
                            terminalMonitor.classList.add('hidden');
                            progressCompact.classList.add('hidden');
                            dragDropArea.classList.remove('hidden');
                            fileInput.value = '';
                        }, 5000);
                    }
                }
            } catch (err) {
                console.error('Error fetching logs:', err);
            }
        }, 1000);
    }

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
            
            const data = await res.json();
            progressFill.style.width = '100%';
            uploadStatusText.textContent = `Mengunggah Selesai! Memulai Pemrosesan...`;
            
            await loadDocuments();
            
            // Mulai tampilkan logs
            startLogPolling(data.filename || file.name);
            
        } catch (e) {
            alert('Error: ' + e.message);
            progressCompact.classList.add('hidden');
            dragDropArea.classList.remove('hidden');
        }
    }
});
