document.addEventListener('DOMContentLoaded', () => {
    // Chat Elements
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('send-btn');
    const chatForm = document.getElementById('chat-form');
    const chatContainer = document.getElementById('chat-container');
    const chatWrapper = document.getElementById('chat-wrapper');
    const welcomeScreen = document.getElementById('welcome-screen');
    const newChatBtn = document.getElementById('new-chat-btn');
    const chatTitle = document.getElementById('chat-title');

    // Sidebar Elements
    const sidebar = document.getElementById('sidebar');
    const closeSidebarBtn = document.getElementById('close-sidebar-btn');
    const openSidebarBtn = document.getElementById('open-sidebar-btn');

    // Auth & Modal Elements
    const sidebarLoginBtn = document.getElementById('sidebar-login-btn');
    const sidebarLogoutBtn = document.getElementById('sidebar-logout-btn');
    const guestCta = document.getElementById('guest-cta');
    const userProfile = document.getElementById('user-profile');
    const historySection = document.getElementById('history-section');
    const loginModal = document.getElementById('login-modal');
    const closeLogin = document.getElementById('close-login');
    const loginForm = document.getElementById('login-form');
    const loginError = document.getElementById('login-error');
    const authTitle = document.getElementById('auth-title');
    const confirmPasswordGroup = document.getElementById('confirm-password-group');
    const confirmPasswordInput = document.getElementById('confirm-password');
    const authSubmitBtn = document.getElementById('auth-submit-btn');
    const authSwitchPrompt = document.getElementById('auth-switch-prompt');
    const authSwitchLink = document.getElementById('auth-switch-link');

    // Docs Explorer Elements
    const exploreDocsBtn = document.getElementById('explore-docs-btn');
    const docsModal = document.getElementById('docs-modal');
    const closeDocs = document.getElementById('close-docs');
    const docsList = document.getElementById('docs-list');
    const docsSearchInput = document.getElementById('docs-search-input');

    // Rename Modal Elements
    const renameModal = document.getElementById('rename-modal');
    const closeRenameBtn = document.getElementById('close-rename');
    const cancelRenameBtn = document.getElementById('cancel-rename');
    const renameForm = document.getElementById('rename-form');
    const newSessionNameInput = document.getElementById('new-session-name');

    // Delete Modal Elements
    const deleteModal = document.getElementById('delete-modal');
    const closeDeleteBtn = document.getElementById('close-delete');
    const cancelDeleteBtn = document.getElementById('cancel-delete');
    const confirmDeleteBtn = document.getElementById('confirm-delete-btn');

    // --- State Management ---
    let currentRole = localStorage.getItem('userRole') || 'guest';
    let currentUsername = localStorage.getItem('username') || '';
    let currentSessionId = localStorage.getItem('currentSessionId') || null;
    let authMode = 'login'; // 'login' atau 'register'

    function getAuthHeaders() {
        const headers = {};
        if (currentUsername) {
            headers['X-User-Username'] = currentUsername;
        }
        return headers;
    }

    function setAuthMode(mode) {
        authMode = mode;
        loginError.classList.add('hidden');
        loginError.textContent = '';
        loginError.style.color = '#E53E3E'; // Red color for errors
        
        if (mode === 'login') {
            authTitle.textContent = 'Silakan Login';
            confirmPasswordGroup.classList.add('hidden');
            confirmPasswordInput.removeAttribute('required');
            authSubmitBtn.textContent = 'Login';
            authSwitchPrompt.textContent = 'Belum punya akun?';
            authSwitchLink.textContent = 'Daftar';
        } else {
            authTitle.textContent = 'Daftar Akun Baru';
            confirmPasswordGroup.classList.remove('hidden');
            confirmPasswordInput.setAttribute('required', 'true');
            authSubmitBtn.textContent = 'Daftar';
            authSwitchPrompt.textContent = 'Sudah punya akun?';
            authSwitchLink.textContent = 'Login';
        }
    }

    function checkAuthState() {
        currentUsername = localStorage.getItem('username') || '';
        if (currentRole === 'admin') {
            window.location.href = 'admin.html';
            return;
        } else if (currentRole === 'user') {
            sidebar.style.display = 'flex';
            historySection.classList.remove('hidden');
            guestCta.classList.add('hidden');
            userProfile.classList.remove('hidden');
            
            // Set dynamic username
            const nameEl = document.querySelector('#user-profile .user-name');
            if (nameEl) {
                nameEl.textContent = currentUsername || 'Mahasiswa';
            }
            // Set dynamic avatar letter
            const avatarEl = document.querySelector('#user-profile .user-avatar');
            if (avatarEl && currentUsername) {
                avatarEl.textContent = currentUsername.charAt(0).toUpperCase();
            }
            
            // Coba memuat history, dan jika ada session_id tersimpan, load session tersebut
            loadHistorySidebar().then(() => {
                if (currentSessionId) {
                    // Coba mencari title dari list history
                    const historyItem = Array.from(document.querySelectorAll('.history-item')).find(
                        item => item.dataset.sessionId === currentSessionId
                    );
                    const title = historyItem ? historyItem.querySelector('.history-text').textContent : "Riwayat Chat";
                    loadSession(currentSessionId, title);
                }
            });
        } else {
            // Guest Mode
            sidebar.style.display = 'flex';
            historySection.classList.add('hidden');
            guestCta.classList.remove('hidden');
            userProfile.classList.add('hidden');
        }
    }

    checkAuthState();

    // --- Auth Logic ---
    sidebarLoginBtn.addEventListener('click', () => {
        setAuthMode('login');
        loginModal.classList.remove('hidden');
        setTimeout(() => document.getElementById('username').focus(), 100);
    });

    closeLogin.addEventListener('click', () => {
        loginModal.classList.add('hidden');
    });

    authSwitchLink.addEventListener('click', (e) => {
        e.preventDefault();
        setAuthMode(authMode === 'login' ? 'register' : 'login');
    });

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('username').value.trim();
        const password = document.getElementById('password').value;

        loginError.classList.add('hidden');
        loginError.textContent = '';
        loginError.style.color = '#E53E3E';

        if (authMode === 'register') {
            const confirmPassword = confirmPasswordInput.value;
            if (password !== confirmPassword) {
                loginError.textContent = 'Konfirmasi password tidak cocok.';
                loginError.classList.remove('hidden');
                return;
            }
            if (password.length < 6) {
                loginError.textContent = 'Password minimal 6 karakter.';
                loginError.classList.remove('hidden');
                return;
            }

            try {
                const res = await fetch('/api/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                
                const data = await res.json();
                if (res.ok) {
                    loginError.style.color = '#10B981'; // Green for success
                    loginError.textContent = 'Registrasi berhasil! Silakan login.';
                    loginError.classList.remove('hidden');
                    document.getElementById('password').value = '';
                    confirmPasswordInput.value = '';
                    setTimeout(() => {
                        setAuthMode('login');
                        document.getElementById('password').focus();
                    }, 1500);
                } else {
                    loginError.textContent = data.detail || 'Registrasi gagal.';
                    loginError.classList.remove('hidden');
                }
            } catch (err) {
                console.error(err);
                loginError.textContent = 'Terjadi kesalahan koneksi server.';
                loginError.classList.remove('hidden');
            }
        } else {
            // Login Mode
            try {
                const res = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                
                const data = await res.json();
                if (res.ok) {
                    localStorage.setItem('userRole', data.role);
                    localStorage.setItem('username', data.username);
                    currentRole = data.role;
                    loginModal.classList.add('hidden');
                    loginForm.reset();
                    checkAuthState();
                    resetChat();
                    
                    if (data.role === 'admin') {
                        window.location.href = 'admin.html';
                    }
                } else {
                    loginError.textContent = data.detail || 'Username atau password salah.';
                    loginError.classList.remove('hidden');
                }
            } catch (err) {
                console.error(err);
                loginError.textContent = 'Terjadi kesalahan koneksi server.';
                loginError.classList.remove('hidden');
            }
        }
    });

    sidebarLogoutBtn.addEventListener('click', () => {
        localStorage.removeItem('userRole');
        localStorage.removeItem('username');
        currentRole = 'guest';
        checkAuthState();
        resetChat();
    });

    // --- Modal Logic ---
    let activeRenameId = null;
    let activeDeleteId = null;

    closeRenameBtn.addEventListener('click', hideRenameModal);
    cancelRenameBtn.addEventListener('click', hideRenameModal);
    
    function hideRenameModal() {
        renameModal.classList.add('hidden');
        activeRenameId = null;
    }

    renameForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const newTitle = newSessionNameInput.value.trim();
        if (activeRenameId && newTitle) {
            try {
                const res = await fetch(`/api/history/${activeRenameId}`, {
                    method: 'PUT',
                    headers: { 
                        'Content-Type': 'application/json',
                        ...getAuthHeaders()
                    },
                    body: JSON.stringify({ title: newTitle })
                });
                if (res.ok) {
                    if (currentSessionId === activeRenameId) {
                        chatTitle.textContent = newTitle;
                    }
                    loadHistorySidebar();
                    hideRenameModal();
                } else {
                    alert('Gagal mengubah nama riwayat.');
                }
            } catch (e) {
                console.error(e);
                alert('Terjadi kesalahan saat mengubah nama riwayat.');
            }
        }
    });

    closeDeleteBtn.addEventListener('click', hideDeleteModal);
    cancelDeleteBtn.addEventListener('click', hideDeleteModal);

    function hideDeleteModal() {
        deleteModal.classList.add('hidden');
        activeDeleteId = null;
    }

    confirmDeleteBtn.addEventListener('click', async () => {
        if (activeDeleteId) {
            try {
                const res = await fetch(`/api/history/${activeDeleteId}`, {
                    method: 'DELETE',
                    headers: getAuthHeaders()
                });
                if (res.ok) {
                    if (currentSessionId === activeDeleteId) {
                        resetChat();
                    }
                    loadHistorySidebar();
                    hideDeleteModal();
                } else {
                    alert('Gagal menghapus riwayat.');
                }
            } catch (e) {
                console.error(e);
                alert('Terjadi kesalahan saat menghapus riwayat.');
            }
        }
    });

    function resetChat() {
        const messages = chatContainer.querySelectorAll('.message');
        messages.forEach(msg => msg.remove());
        welcomeScreen.style.display = 'block';
        chatTitle.textContent = "Chat Baru";
        
        currentSessionId = null;
        localStorage.removeItem('currentSessionId');

        document.querySelectorAll('.history-item').forEach(hi => hi.classList.remove('active'));
    }

    // --- Sidebar Toggle Logic ---
    closeSidebarBtn.addEventListener('click', () => {
        sidebar.classList.add('collapsed');
        openSidebarBtn.classList.remove('hidden');
    });

    openSidebarBtn.addEventListener('click', () => {
        sidebar.classList.remove('collapsed');
        openSidebarBtn.classList.add('hidden');
    });

    // --- Docs Explorer Logic ---
    let realDocs = [];

    exploreDocsBtn.addEventListener('click', async () => {
        docsModal.classList.remove('hidden');
        renderDocsList(realDocs);
        setTimeout(() => docsSearchInput.focus(), 100);
        
        try {
            const res = await fetch('/api/documents');
            if (res.ok) {
                const data = await res.json();
                realDocs = data.documents;
                renderDocsList(realDocs);
            }
        } catch (e) {
            console.error('Failed to load documents', e);
        }
    });

    closeDocs.addEventListener('click', () => {
        docsModal.classList.add('hidden');
    });

    docsSearchInput.addEventListener('input', (e) => {
        const keyword = e.target.value.toLowerCase();
        const filtered = realDocs.filter(d => d.title.toLowerCase().includes(keyword) || d.file.toLowerCase().includes(keyword));
        renderDocsList(filtered);
    });

    function renderDocsList(docs) {
        docsList.innerHTML = '';
        if (docs.length === 0) {
            docsList.innerHTML = '<p style="text-align:center; color: var(--text-muted); font-size: 13px; padding: 20px 0;">Dokumen tidak ditemukan.</p>';
            return;
        }
        docs.forEach(doc => {
            const li = document.createElement('li');
            li.className = 'doc-item';
            li.innerHTML = `
                <div class="doc-item-icon"><i class="ph-fill ph-file-pdf"></i></div>
                <div class="doc-item-info">
                    <h4>${escapeHTML(doc.title)}</h4>
                    <p>${escapeHTML(doc.file)}</p>
                </div>
            `;
            li.addEventListener('click', () => {
                window.open('/uploads/' + encodeURIComponent(doc.file), '_blank');
            });
            docsList.appendChild(li);
        });
    }

    // --- Real History Management will be loaded dynamically ---

    // --- Chat Logic ---
    chatInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 200) + 'px';
        if (this.value.trim() !== '') {
            sendBtn.removeAttribute('disabled');
        } else {
            sendBtn.setAttribute('disabled', 'true');
        }
    });

    chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const message = chatInput.value.trim();
        if (message) {
            sendMessage(message);
        }
    });

    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    newChatBtn.addEventListener('click', () => {
        resetChat();
        currentSessionId = null;
        if (window.innerWidth < 768 && currentRole !== 'guest') {
            sidebar.classList.add('collapsed');
            openSidebarBtn.classList.remove('hidden');
        }
    });

    async function sendMessage(text) {
        if (welcomeScreen.style.display !== 'none') {
            welcomeScreen.style.display = 'none';
        }

        // If it's a new chat, we might set title temporarily
        if (chatTitle.textContent === 'Chat Baru') {
            chatTitle.textContent = text.length > 20 ? text.substring(0, 20) + "..." : text;
        }

        addUserMessage(text);

        chatInput.value = '';
        chatInput.style.height = 'auto';
        sendBtn.setAttribute('disabled', 'true');

        const typingId = addTypingIndicator();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    ...getAuthHeaders()
                },
                body: JSON.stringify({ message: text, session_id: currentSessionId })
            });
            
            if (!response.ok) {
                throw new Error('Gagal menghubungi server');
            }
            
            const data = await response.json();
            currentSessionId = data.session_id;
            removeMessage(typingId);
            addSystemMessage(data);
            
            // Refresh history sidebar
            loadHistorySidebar();
        } catch (error) {
            removeMessage(typingId);
            addSystemMessage({ answer: 'Maaf, terjadi kesalahan saat menghubungi server: ' + error.message });
        }
    }

    function addUserMessage(text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message user-message';
        msgDiv.innerHTML = `
            <div class="message-content">
                <p>${escapeHTML(text)}</p>
            </div>
        `;
        chatContainer.appendChild(msgDiv);
        scrollToBottom();
    }

    function addSystemMessage(responseObj) {
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message system-message';

        let markdownText = typeof responseObj === 'string' ? responseObj : responseObj.answer;
        const parsedContent = typeof marked !== 'undefined' ? marked.parse(markdownText) : `<p>${escapeHTML(markdownText)}</p>`;

        let sourcesHtml = '';
        if (typeof responseObj === 'object' && responseObj.sources && responseObj.sources.length > 0) {
            sourcesHtml = '<div class="source-references">';
            responseObj.sources.forEach(src => {
                sourcesHtml += `
                    <div class="source-pill" title="Buka Dokumen: ${escapeHTML(src.file)}" onclick="window.open('/uploads/' + encodeURIComponent('${src.file}'), '_blank')">
                        <i class="ph-bold ph-file-text"></i>
                        <span>${escapeHTML(src.title)}</span>
                    </div>
                `;
            });
            sourcesHtml += '</div>';
        }

        msgDiv.innerHTML = `
            <div class="avatar"><i class="ph ph-sparkle"></i></div>
            <div class="message-content">
                ${parsedContent}
                ${sourcesHtml}
            </div>
        `;
        chatContainer.appendChild(msgDiv);
        scrollToBottom();
    }

    function addTypingIndicator() {
        const id = 'typing-' + Date.now();
        const msgDiv = document.createElement('div');
        msgDiv.className = 'message system-message';
        msgDiv.id = id;
        msgDiv.innerHTML = `
            <div class="avatar"><i class="ph ph-sparkle"></i></div>
            <div class="message-content">
                <div class="typing-indicator">
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                    <div class="typing-dot"></div>
                </div>
            </div>
        `;
        chatContainer.appendChild(msgDiv);
        scrollToBottom();
        return id;
    }

    function removeMessage(id) {
        const el = document.getElementById(id);
        if (el) el.remove();
    }

    function scrollToBottom() {
        chatWrapper.scrollTop = chatWrapper.scrollHeight;
    }

    function escapeHTML(str) {
        return str.replace(/[&<>'"]/g,
            tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
        );
    }

    // --- Dynamic API Fetch for History ---
    async function loadHistorySidebar() {
        if (currentRole === 'guest') return;
        try {
            const res = await fetch('/api/history', {
                headers: getAuthHeaders()
            });
            if (!res.ok) return;
            const data = await res.json();
            const historyList = document.querySelector('.history-list');
            if (historyList) {
                historyList.innerHTML = '';
                data.sessions.forEach(session => {
                    const li = document.createElement('li');
                    li.className = 'history-item';
                    li.dataset.sessionId = session.session_id;
                    if (session.session_id === currentSessionId) li.classList.add('active');
                    li.innerHTML = `
                        <i class="ph ph-chat-text" style="flex-shrink: 0; margin-right: 8px;"></i>
                        <span class="history-text">${escapeHTML(session.title)}</span>
                        <div class="history-actions">
                            <button class="icon-btn edit-session-btn" title="Ubah Nama"><i class="ph ph-pencil-simple"></i></button>
                            <button class="icon-btn delete-session-btn" title="Hapus"><i class="ph ph-trash"></i></button>
                        </div>
                    `;
                    
                    // Click listener for the item to load session
                    li.addEventListener('click', (e) => {
                        // Jangan load jika yang di-klik adalah tombol action
                        if (e.target.closest('.history-actions')) return;
                        loadSession(session.session_id, session.title);
                    });
                    
                    // Click listeners for actions
                    const editBtn = li.querySelector('.edit-session-btn');
                    editBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        renameSession(session.session_id, session.title);
                    });
                    
                    const deleteBtn = li.querySelector('.delete-session-btn');
                    deleteBtn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        deleteSession(session.session_id);
                    });
                    
                    historyList.appendChild(li);
                });
            }
        } catch(e) {
            console.error('Error loading history', e);
        }
    }
    
    async function renameSession(sessionId, oldTitle) {
        activeRenameId = sessionId;
        newSessionNameInput.value = oldTitle;
        renameModal.classList.remove('hidden');
        setTimeout(() => newSessionNameInput.focus(), 100);
    }

    async function deleteSession(sessionId) {
        activeDeleteId = sessionId;
        deleteModal.classList.remove('hidden');
    }
    
    async function loadSession(sessionId, title) {
        try {
            const res = await fetch(`/api/history/${sessionId}`, {
                headers: getAuthHeaders()
            });
            if (!res.ok) throw new Error('Failed to load session');
            const data = await res.json();
            
            resetChat();
            welcomeScreen.style.display = 'none';
            chatTitle.textContent = title || "Riwayat Chat";
            currentSessionId = sessionId;
            localStorage.setItem('currentSessionId', sessionId);
            
            data.messages.forEach(msg => {
                if (msg.role === 'user') {
                    addUserMessage(msg.content);
                } else {
                    addSystemMessage({ answer: msg.content, sources: msg.sources });
                }
            });
            loadHistorySidebar();
        } catch (e) {
            alert("Gagal memuat sesi chat.");
        }
    }

});

