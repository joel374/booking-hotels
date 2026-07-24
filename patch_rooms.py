import sys

with open('templates/admin/rooms.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. CSS
css_addition = """
.room-dropdown button:hover,
.room-dropdown .dropdown-button:hover {
    background: rgba(37, 99, 235, 0.06);
}
.room-pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.6rem;
    margin-top: 1.75rem;
}
.room-pagination[hidden] {
    display: none;
}
.room-pagination button {
    min-width: 44px;
    height: 44px;
    padding: 0 0.9rem;
    border: 1px solid var(--border);
    border-radius: 14px;
    background: #fff;
    color: var(--text);
    cursor: pointer;
    transition: var(--transition);
}
.room-pagination button:hover:not(:disabled) {
    border-color: rgba(79, 70, 229, 0.3);
    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.08);
    transform: translateY(-1px);
}
.room-pagination button.is-active {
    background: var(--secondary);
    border-color: var(--secondary);
    color: #fff;
}
.room-pagination button:disabled {
    cursor: not-allowed;
    opacity: 0.45;
}
.room-pagination .pagination-dots {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 44px;
    height: 44px;
    padding: 0 0.9rem;
    color: var(--subtext);
    font-weight: 600;
}
</style>"""

content = content.replace("""
.room-dropdown button:hover,
.room-dropdown .dropdown-button:hover {
    background: rgba(37, 99, 235, 0.06);
}
</style>""", css_addition)

# 2. HTML Nav
html_addition = """
    {% else %}
    <div style="grid-column:1 / -1; padding:2rem; text-align:center; color: var(--subtext);">No rooms in database.</div>
    {% endfor %}
</div>

<nav id="room-pagination" class="room-pagination" aria-label="Room pagination" hidden></nav>

<div id="modalAddRoom" class="modal">"""

content = content.replace("""
    {% else %}
    <div style="grid-column:1 / -1; padding:2rem; text-align:center; color: var(--subtext);">No rooms in database.</div>
    {% endfor %}
</div>

<div id="modalAddRoom" class="modal">""", html_addition)

# 3. JavaScript
js_old = """
function initRoomPage() {
    const searchInput = document.getElementById('rooms-search');
    const categorySelect = document.getElementById('rooms-category');
    const sortSelect = document.getElementById('rooms-sort');
    const cards = Array.from(document.querySelectorAll('.room-card'));

    const updateCards = () => {
        const query = searchInput.value.trim().toLowerCase();
        const category = categorySelect.value;

        cards.forEach(card => {
            const text = `${card.dataset.name} ${card.dataset.location}`;
            const hasImages = parseInt(card.dataset.images || '0', 10) > 0;
            let visible = true;

            if (query && !text.includes(query)) visible = false;
            if (category === 'has_images' && !hasImages) visible = false;
            if (category === 'no_images' && hasImages) visible = false;

            card.style.display = visible ? 'flex' : 'none';
        });
        sortCards();
    };

    const sortCards = () => {
        const container = document.querySelector('.room-grid');
        const visibleCards = cards.filter(card => card.style.display !== 'none');
        const order = sortSelect.value;

        if (order === 'name_asc') {
            visibleCards.sort((a, b) => a.dataset.name.localeCompare(b.dataset.name));
        } else if (order === 'name_desc') {
            visibleCards.sort((a, b) => b.dataset.name.localeCompare(a.dataset.name));
        } else {
            visibleCards.sort((a, b) => parseInt(a.dataset.index, 10) - parseInt(b.dataset.index, 10));
        }

        visibleCards.forEach(card => container.appendChild(card));
    };

    searchInput.addEventListener('input', updateCards);
    categorySelect.addEventListener('change', updateCards);
    sortSelect.addEventListener('change', updateCards);
    updateCards();
"""

js_new = """
function initRoomPage() {
    const searchInput = document.getElementById('rooms-search');
    const categorySelect = document.getElementById('rooms-category');
    const sortSelect = document.getElementById('rooms-sort');
    const cards = Array.from(document.querySelectorAll('.room-card'));
    const grid = document.querySelector('.room-grid');
    const pagination = document.getElementById('room-pagination');
    const pageSize = 12;
    let currentPage = 1;
    let filteredCards = [...cards];

    const sortCards = () => {
        const order = sortSelect.value;
        filteredCards.sort((a, b) => {
            if (order === 'name_asc') return a.dataset.name.localeCompare(b.dataset.name);
            if (order === 'name_desc') return b.dataset.name.localeCompare(a.dataset.name);
            return parseInt(a.dataset.index, 10) - parseInt(b.dataset.index, 10);
        });
    };

    const renderPagination = () => {
        const pageCount = Math.ceil(filteredCards.length / pageSize);
        pagination.replaceChildren();
        pagination.hidden = pageCount <= 1;
        if (pageCount <= 1) return;

        const addButton = (label, page, disabled = false, active = false, isDots = false) => {
            const button = document.createElement(isDots ? 'span' : 'button');
            if (!isDots) button.type = 'button';
            button.textContent = label;
            if (!isDots) {
                button.disabled = disabled;
                button.classList.toggle('is-active', active);
                button.setAttribute('aria-label', label);
                if (active) button.setAttribute('aria-current', 'page');
                button.addEventListener('click', () => {
                    currentPage = page;
                    renderPage();
                    pagination.scrollIntoView({ block: 'nearest' });
                });
            } else {
                button.className = 'pagination-dots';
            }
            pagination.appendChild(button);
        };

        addButton('Previous', currentPage - 1, currentPage === 1);

        let startPage = Math.max(1, currentPage - 2);
        let endPage = Math.min(pageCount, currentPage + 2);
        
        if (currentPage <= 3) endPage = Math.min(pageCount, 5);
        if (currentPage >= pageCount - 2) startPage = Math.max(1, pageCount - 4);

        if (startPage > 1) {
            addButton('1', 1);
            if (startPage > 2) addButton('...', null, false, false, true);
        }

        for (let page = startPage; page <= endPage; page++) {
            addButton(String(page), page, false, page === currentPage);
        }

        if (endPage < pageCount) {
            if (endPage < pageCount - 1) addButton('...', null, false, false, true);
            addButton(String(pageCount), pageCount);
        }

        addButton('Next', currentPage + 1, currentPage === pageCount);
    };

    const renderPage = () => {
        const pageCount = Math.max(1, Math.ceil(filteredCards.length / pageSize));
        currentPage = Math.min(currentPage, pageCount);
        const start = (currentPage - 1) * pageSize;
        const pageCards = filteredCards.slice(start, start + pageSize);

        cards.forEach(card => { card.style.display = 'none'; });
        pageCards.forEach(card => {
            card.style.display = 'flex';
            grid.appendChild(card);
        });
        renderPagination();
    };

    const updateCards = (resetPage = true) => {
        const query = searchInput.value.trim().toLowerCase();
        const category = categorySelect.value;

        filteredCards = cards.filter(card => {
            const name = card.dataset.name || '';
            const location = card.dataset.location || '';
            const hasImages = parseInt(card.dataset.images || '0', 10) > 0;
            return (!query || `${name} ${location}`.includes(query))
                && !(category === 'has_images' && !hasImages)
                && !(category === 'no_images' && hasImages);
        });
        if (resetPage) currentPage = 1;
        sortCards();
        renderPage();
    };

    searchInput.addEventListener('input', () => updateCards(true));
    categorySelect.addEventListener('change', () => updateCards(true));
    sortSelect.addEventListener('change', () => updateCards(true));
    updateCards(true);
"""

content = content.replace(js_old.strip(), js_new.strip())

with open('templates/admin/rooms.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Patch applied successfully.")
