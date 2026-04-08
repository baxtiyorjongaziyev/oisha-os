const tg = window.Telegram.WebApp;
const container = document.getElementById('portfolio-container');
const modal = document.getElementById('modal');
const closeBtn = document.querySelector('.close-btn');

// Initialize Telegram WebApp
tg.expand();
tg.ready();

// Set user name in header
const user = tg.initDataUnsafe?.user;
if (user) {
    document.getElementById('user-name').innerText = `JonBranding x ${user.first_name}`;
}

// Telegram Login Widget Callback
function onTelegramAuth(user) {
    console.log("Logged in as:", user.first_name, user.id);
    // Send to backend or show success
    alert(`Xush kelibsiz, ${user.first_name}!`);
    document.getElementById('login-widget-container').innerHTML = `<span>✅ ${user.first_name} sifatida kirdingiz</span>`;
}
window.onTelegramAuth = onTelegramAuth;

// Fetch and render portfolio data
async function loadPortfolio() {
    try {
        const response = await fetch('data.json');
        const data = await response.json();
        renderProjects(data);
    } catch (error) {
        console.error('Data loading error:', error);
        container.innerHTML = '<p style="color: red;">Ma\'lumot yuklashda xato yuz berdi.</p>';
    }
}

function renderProjects(projects) {
    container.innerHTML = '';
    projects.forEach(project => {
        const card = document.createElement('div');
        card.className = 'card';
        card.innerHTML = `
            <img src="${project.image}" alt="${project.title}">
            <div class="card-info">
                <h3>${project.title}</h3>
                <span class="category-badge">${project.category}</span>
            </div>
        `;
        card.addEventListener('click', () => showDetails(project));
        container.appendChild(card);
    });
}

function showDetails(project) {
    document.getElementById('modal-image').src = project.image;
    document.getElementById('modal-title').innerText = project.title;
    document.getElementById('modal-category').innerText = project.category;
    document.getElementById('modal-description').innerText = project.description;
    document.getElementById('modal-link').href = project.link;

    modal.classList.remove('hidden');

    // Telegram Main Button logic
    tg.MainButton.setText('Loyihaga o\'tish');
    tg.MainButton.show();
    tg.MainButton.onClick(() => window.open(project.link, '_blank'));
}

closeBtn.onclick = () => {
    modal.classList.add('hidden');
    tg.MainButton.hide();
};

window.onclick = (event) => {
    if (event.target == modal) {
        modal.classList.add('hidden');
        tg.MainButton.hide();
    }
};

// Start loading
loadPortfolio();
