/* =============================================
   PENCA TUYA MUNDIAL 2026 - App JS
   ============================================= */

const API = '';  // same origin

// ===== STATE =====
let currentUser = null;
let currentToken = null;
let currentPhase = 'group';
let currentMatchForPred = null;
let selectedKoWinner = null;

// ===== INIT =====
document.addEventListener('DOMContentLoaded', () => {
  loadAuth();
  loadTop3();
  loadHomeUpcoming();
  loadHomeCountdown();

  // Fixture tab buttons
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentPhase = btn.dataset.phase;
      loadFixture(currentPhase);
    });
  });

  // Route from URL hash
  const fullHash = window.location.hash.replace('#', '') || 'home';
  const hash = fullHash.split('?')[0];
  window._resetToken = fullHash.startsWith('reset-password') ? new URLSearchParams(fullHash.split('?')[1] || '').get('token') : null;
    navigate(hash);
    if (window._resetToken) { setTimeout(() => { const el = document.getElementById('resetToken'); if (el) el.value = window._resetToken; }, 100); }
});

// ===== AUTH =====
function loadAuth() {
  currentToken = localStorage.getItem('penca_token');
  const userData = localStorage.getItem('penca_user');
  if (currentToken && userData) {
    try {
      currentUser = JSON.parse(userData);
      renderNavAuth();
    } catch {
      logout();
    }
  } else {
    renderNavAuth();
  }
}

function renderNavAuth() {
  const el = document.getElementById('navAuth');
  if (currentUser) {
    el.innerHTML = `
      <span style="color:#aaa;font-size:0.8rem;font-weight:500">${currentUser.username}</span>
      <button class="btn-primary btn-sm dark" onclick="navigate('profile')">Mi perfil</button>
      <button class="btn-secondary btn-sm" onclick="logout()">Salir</button>
    `;
    // Hide hero CTA and show personalized version
    const heroCta = document.getElementById('heroCta');
    if (heroCta) {
      heroCta.innerHTML = `
        <button class="btn-primary" onclick="navigate('fixture')">VER FIXTURE</button>
        <button class="btn-secondary" onclick="navigate('ranking')">Mi Ranking</button>
      `;
    }
    // Show admin if admin
    if (currentUser.is_admin) {
      el.innerHTML += `<button class="btn-primary btn-sm" onclick="navigate('admin')" style="background:var(--gold);color:var(--black)">Admin</button>`;
    }
  } else {
    el.innerHTML = `
      <button class="btn-secondary btn-sm" onclick="navigate('login')">Entrar</button>
      <button class="btn-primary btn-sm dark" onclick="navigate('register')">Registrarse</button>
    `;
  }
}

function logout() {
  localStorage.removeItem('penca_token');
  localStorage.removeItem('penca_user');
  currentUser = null;
  currentToken = null;
  renderNavAuth();
  navigate('home');
  showToast('Sesión cerrada');
}

// ===== NAVIGATION =====
function navigate(page, param) {
  closeMenu();
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const target = document.getElementById(`page-${page}`);
  if (target) {
    target.classList.add('active');
    target.style.removeProperty('display');
    window.scrollTo(0, 0);
    window.location.hash = page;
  }

  // Load page data
  if (page === 'home') { loadHomeUpcoming(); loadHomeCountdown(); }
  if (page === 'fixture') loadFixture(currentPhase);
  if (page === 'ranking') loadRanking();
  if (page === 'groups') loadGroups();
  if (page === 'profile') loadProfile();
  if (page === 'admin') loadAdmin();
  if (page === 'prizes') {} // static
  if (page === 'rival') loadRivalProfile(param);
}

function toggleMenu() {
  const menu = document.getElementById('navMenu');
  const btn = document.getElementById('menuToggle');
  if (!menu) return;
  menu.classList.toggle('open');
  if (btn) btn.textContent = menu.classList.contains('open') ? '✕' : '☰';
}

function closeMenu() {
  const menu = document.getElementById('navMenu');
  const btn = document.getElementById('menuToggle');
  if (menu) menu.classList.remove('open');
  if (btn) btn.textContent = '☰';
}

function adjustScore(id, delta) {
  const el = document.getElementById(id);
  if (!el) return;
  const current = parseInt(el.dataset.value || 0);
  const next = Math.max(0, current + delta);
  el.dataset.value = next;
  el.textContent = next;
}

// ===== HOME COUNTDOWN =====
let _countdownInterval = null;
let _upcomingMatches = [];

async function loadHomeCountdown() {
  // Load upcoming matches for countdown
  try {
    const data = await apiFetch('/api/matches/upcoming?limit=5');
    _upcomingMatches = Array.isArray(data) ? data : (data.matches || []);
  } catch {}
  _startCountdown();
}

function _startCountdown() {
  if (_countdownInterval) clearInterval(_countdownInterval);
  _tickCountdown();
  _countdownInterval = setInterval(_tickCountdown, 1000);
}

function _tickCountdown() {
  const timerEl   = document.getElementById('countdownTimer');
  const labelEl   = document.getElementById('countdownLabel');
  const noteEl    = document.getElementById('countdownNote');
  const cardEl    = document.getElementById('countdownCard');
  const matchEl   = document.getElementById('countdownMatchInfo');
  // Fixture compact elements
  const fTimerEl  = document.getElementById('fixtureCountdownTimer');
  const fLabelEl  = document.getElementById('fixtureCountdownLabel');
  const fMatchEl  = document.getElementById('fixtureCountdownMatch');

  if (!timerEl && !fTimerEl) { clearInterval(_countdownInterval); return; }

  const now = Date.now();
  const nextMatch = _upcomingMatches.find(m => {
    if (!m.match_date) return false;
    if (m.status === 'finished' || m.status === 'live') return false;
    return new Date(m.match_date).getTime() > now;
  });

  if (!nextMatch) {
    const emptyTimer = '<span class="cd-sep">--</span>';
    if (timerEl) timerEl.innerHTML = emptyTimer;
    if (fTimerEl) fTimerEl.innerHTML = emptyTimer;
    if (labelEl) labelEl.textContent = 'Próximo partido';
    if (noteEl) noteEl.textContent = 'El próximo partido aún no tiene fecha confirmada.';
    return;
  }

  const target = new Date(nextMatch.match_date).getTime();
  const diff = target - now;

  if (diff <= 0) {
    _upcomingMatches = _upcomingMatches.filter(m => m !== nextMatch);
    _tickCountdown();
    return;
  }

  const totalSecs = Math.floor(diff / 1000);
  const days  = Math.floor(totalSecs / 86400);
  const hours = Math.floor((totalSecs % 86400) / 3600).toString().padStart(2, '0');
  const mins  = Math.floor((totalSecs % 3600) / 60).toString().padStart(2, '0');
  const secs  = (totalSecs % 60).toString().padStart(2, '0');
  const sep   = '<span class="cd-sep"> · </span>';

  const timeHtml = days > 0
    ? `${days}d${sep}${hours}:${mins}:${secs}`
    : `${hours}:${mins}:${secs}`;

  // Build match info line for home countdown
  const homeTeam = nextMatch.home_team || {};
  const awayTeam = nextMatch.away_team || {};
  const homeName = homeTeam.name || nextMatch.home_team_placeholder || '?';
  const awayName = awayTeam.name || nextMatch.away_team_placeholder || '?';
  const homeFlag = teamFlag(homeTeam.code || '');
  const awayFlag = teamFlag(awayTeam.code || '');
  const dateStr  = nextMatch.match_date ? formatMatchDate(nextMatch.match_date) : '';
  const matchInfoHtml = `${homeFlag} ${escHtml(homeName)} <span style="color:var(--celeste);margin:0 0.3em">VS</span> ${escHtml(awayName)} ${awayFlag}<br><small style="color:#aaa">${dateStr}</small>`;

  const isUrgent = diff < 30 * 60 * 1000;

  // ─ Home countdown ─
  if (timerEl) timerEl.innerHTML = timeHtml;

  const matchInfoEl = document.getElementById('countdownMatchInfo');
  if (matchInfoEl) matchInfoEl.innerHTML = matchInfoHtml;

  if (isUrgent) {
    const minsLeft = Math.ceil(diff / 60000);
    if (labelEl) labelEl.textContent = '⚠️ ¡Último momento!';
    if (noteEl) { noteEl.textContent = `Cerramos pronósticos en ${minsLeft} minuto${minsLeft !== 1 ? 's' : ''}.`; noteEl.classList.add('urgent'); }
    if (timerEl) timerEl.classList.add('urgent');
    if (cardEl)  cardEl.classList.add('urgent');
  } else {
    if (labelEl) labelEl.textContent = 'Próximo partido';
    if (noteEl)  { noteEl.textContent = 'Tenés hasta 30 minutos antes del inicio de cada partido para editar tu pronóstico.'; noteEl.classList.remove('urgent'); }
    if (timerEl) timerEl.classList.remove('urgent');
    if (cardEl)  cardEl.classList.remove('urgent');
  }

  // ─ Fixture compact countdown ─
  if (fTimerEl) fTimerEl.innerHTML = timeHtml;
  if (fLabelEl) fLabelEl.textContent = isUrgent ? '⚠️ Cierra pronto' : 'Próximo partido';
  if (fMatchEl) fMatchEl.textContent = `${homeFlag} ${homeName} vs ${awayName} ${awayFlag}`;
  if (fTimerEl) { isUrgent ? fTimerEl.classList.add('urgent') : fTimerEl.classList.remove('urgent'); }
}

// ===== HOME UPCOMING =====
async function loadHomeUpcoming() {
  const container = document.getElementById('homeUpcoming');
  if (!container) return;
  try {
    const token = currentToken ? `Bearer ${currentToken}` : null;
    const data = await apiFetch('/api/matches/upcoming?limit=3', {}, token);
    const matches = Array.isArray(data) ? data : (data.matches || []);
    // Also update _upcomingMatches for countdown if empty
    if (!_upcomingMatches.length) _upcomingMatches = matches;

    if (!matches.length) {
      container.innerHTML = '<p class="empty-state">No hay partidos próximos confirmados aún.</p>';
      return;
    }

    container.innerHTML = matches.map(m => {
      const homeTeam = m.home_team || {};
      const awayTeam = m.away_team || {};
      const homeName = homeTeam.name || m.home_team_placeholder || '?';
      const awayName = awayTeam.name || m.away_team_placeholder || '?';
      const homeFlag = teamFlagHtml(homeTeam);
      const awayFlag = teamFlagHtml(awayTeam);
      const dateStr = m.match_date ? formatMatchDate(m.match_date) : 'Fecha a confirmar';
      const pred = m.user_prediction;
      const isLocked = m.predictions_locked;
      // Cierre 30 min antes del partido
      const matchDateH = m.match_date ? new Date(m.match_date) : null;
      const isClosed = isLocked || (matchDateH && Date.now() >= matchDateH.getTime() - 30 * 60 * 1000);

      let btnHtml = '';
      if (!isClosed) {
        if (currentUser) {
          const label = pred ? '✏️ Editar pronóstico' : 'Pronosticar';
          const cls = pred ? 'home-mc-btn' : 'home-mc-btn';
          btnHtml = `<button class="${cls}" onclick="openPredModal(${JSON.stringify(m).replace(/"/g, '&quot;')})">${label}</button>`;
        } else {
          btnHtml = `<button class="home-mc-btn secondary" onclick="navigate('register')">Registrate para pronosticar</button>`;
        }
      } else if (isClosed && !isFinished && !isLive) {
        btnHtml = `<span class="match-closed-badge">🔒 Pronósticos cerrados</span>`;
      }

      return `<div class="home-match-card">
        <div class="home-mc-teams">
          <div class="home-mc-team">
            <span class="home-mc-flag">${homeFlag}</span>
            <span class="home-mc-name">${escHtml(homeName)}</span>
          </div>
          <span class="home-mc-vs">VS</span>
          <div class="home-mc-team away">
            <span class="home-mc-flag">${awayFlag}</span>
            <span class="home-mc-name">${escHtml(awayName)}</span>
          </div>
        </div>
        <div class="home-mc-date">${dateStr}</div>
        ${btnHtml}
      </div>`;
    }).join('');

  } catch {
    const container2 = document.getElementById('homeUpcoming');
    if (container2) container2.innerHTML = '<p class="empty-state">Error cargando partidos.</p>';
  }
}

// ===== HOME STATS =====
async function loadHomeStats() {
  try {
    const data = await apiFetch('/api/ranking/stats');
    document.getElementById('statParticipants').textContent = data.total_participants.toLocaleString();
    document.getElementById('statMatches').textContent = data.matches_played.toLocaleString();
    document.getElementById('statPredictions').textContent = data.total_predictions.toLocaleString();
  } catch {}
}

async function loadTop3() {
  try {
    const data = await apiFetch('/api/ranking/top3');
    const container = document.getElementById('top3Container');
    if (!data || data.length === 0) {
      container.innerHTML = '<p class="empty-state">El ranking estará disponible cuando arranque el mundial 🏟️</p>';
      return;
    }
    const medals = ['🥇', '🥈', '🥉'];
    const posClasses = ['gold', 'silver', 'bronze'];
    container.innerHTML = `
      <div class="top3-grid">
        ${data.map((u, i) => `
          <div class="top3-card">
            <div class="top3-pos">${medals[i]}</div>
            <div class="top3-username">${escHtml(u.username)}</div>
            <div class="top3-points">${u.total_points} <small style="font-size:0.7rem;color:var(--gray)">pts</small></div>
          </div>
        `).join('')}
      </div>
    `;
  } catch {}
}

// ===== GROUPS =====
async function loadGroups() {
  const container = document.getElementById('groupsContent');
  if (!container) return;
  container.innerHTML = '<div class="loading">Cargando tablas de posiciones...</div>';

  const staticGroups = [
    { group: 'A', teams: [
      { name: 'México',              code: 'MEX', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Sudáfrica',           code: 'RSA', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Rep. de Corea',       code: 'KOR', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Chequia',             code: 'CZE', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 }
    ]},
    { group: 'B', teams: [
      { name: 'Canadá',              code: 'CAN', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Bosnia y Herzegovina',code: 'BIH', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Catar',               code: 'QAT', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Suiza',               code: 'SUI', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 }
    ]},
    { group: 'C', teams: [
      { name: 'Brasil',              code: 'BRA', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Marruecos',           code: 'MAR', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Haití',               code: 'HAI', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Escocia',             code: 'SCO', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 }
    ]},
    { group: 'D', teams: [
      { name: 'EE. UU.',             code: 'USA', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Paraguay',            code: 'PAR', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Australia',           code: 'AUS', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Turquía',             code: 'TUR', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 }
    ]},
    { group: 'E', teams: [
      { name: 'Alemania',            code: 'GER', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Curazao',             code: 'CUW', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Costa de Marfil',     code: 'CIV', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Ecuador',             code: 'ECU', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 }
    ]},
    { group: 'F', teams: [
      { name: 'Países Bajos',        code: 'NED', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Japón',               code: 'JPN', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Suecia',              code: 'SWE', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Túnez',               code: 'TUN', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 }
    ]},
    { group: 'G', teams: [
      { name: 'Bélgica',             code: 'BEL', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Egipto',              code: 'EGY', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'RI de Irán',          code: 'IRN', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Nueva Zelanda',       code: 'NZL', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 }
    ]},
    { group: 'H', teams: [
      { name: 'España',              code: 'ESP', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Is. Cabo Verde',      code: 'CPV', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Arabia Saudí',        code: 'KSA', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Uruguay',             code: 'URU', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 }
    ]},
    { group: 'I', teams: [
      { name: 'Francia',             code: 'FRA', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Senegal',             code: 'SEN', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Irak',                code: 'IRQ', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Noruega',             code: 'NOR', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 }
    ]},
    { group: 'J', teams: [
      { name: 'Argentina',           code: 'ARG', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Argelia',             code: 'ALG', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Austria',             code: 'AUT', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Jordania',            code: 'JOR', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 }
    ]},
    { group: 'K', teams: [
      { name: 'Portugal',            code: 'POR', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'RD Congo',            code: 'COD', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Uzbekistán',          code: 'UZB', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Colombia',            code: 'COL', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 }
    ]},
    { group: 'L', teams: [
      { name: 'Inglaterra',          code: 'ENG', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Croacia',             code: 'CRO', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Ghana',               code: 'GHA', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 },
      { name: 'Panamá',              code: 'PAN', p:0,w:0,d:0,l:0,gf:0,ga:0,pts:0 }
    ]}
  ];

  // Extra flags for new teams not in the original teamFlag() map
  const extraFlags = {
    'BIH': '🇧🇦', 'QAT': '🇶🇦', 'SUI': '🇨🇭', 'HAI': '🇭🇹',
    'PAR': '🇵🇾', 'CUW': '🇨🇼', 'CIV': '🇨🇮', 'SWE': '🇸🇪',
    'TUN': '🇹🇳', 'EGY': '🇪🇬', 'NZL': '🇳🇿', 'CPV': '🇨🇻',
    'NOR': '🇳🇴', 'ALG': '🇩🇿', 'JOR': '🇯🇴', 'COD': '🇨🇩',
    'GHA': '🇬🇭', 'RSA': '🇿🇦', 'KOR': '🇰🇷', 'CZE': '🇨🇿', 'KSA': '🇸🇦',
    'IRQ': '🇮🇶', 'UZB': '🇺🇿', 'SCO': '🏴󠁧󠁢󠁳󠁣󠁴󠁿', 'TUR': '🇹🇷', 'IRN': '🇮🇷'
  };

  function getFlag(code) {
    if (extraFlags[code]) return extraFlags[code];
    return teamFlag(code);
  }

  let groups = staticGroups; // siempre usar fallback estático hasta verificar Sportmonks

  function renderGroupTable(groupData) {
    const rows = groupData.teams.map((t) => {
      const gd = (t.gf || 0) - (t.ga || 0);
      const flag = getFlag(t.code);
      return `<tr>
        <td class="standings-flag">${flag}</td>
        <td class="standings-team">${escHtml(t.name)}</td>
        <td>${t.p || 0}</td>
        <td>${t.w || 0}</td>
        <td>${t.d || 0}</td>
        <td>${t.l || 0}</td>
        <td>${t.gf || 0}</td>
        <td>${t.ga || 0}</td>
        <td>${gd >= 0 ? '+' + gd : gd}</td>
        <td class="standings-pts">${t.pts || 0}</td>
      </tr>`;
    }).join('');
    return `<div class="group-standings-card">
      <div class="group-label">Grupo ${groupData.group}</div>
      <table class="standings-table">
        <colgroup>
          <col class="col-flag" />
          <col class="col-name" />
          <col class="col-num" /><col class="col-num" /><col class="col-num" /><col class="col-num" />
          <col class="col-num" /><col class="col-num" /><col class="col-num" />
          <col class="col-pts" />
        </colgroup>
        <thead>
          <tr>
            <th></th>
            <th class="col-name-header">Equipo</th>
            <th>PJ</th>
            <th>G</th>
            <th>E</th>
            <th>P</th>
            <th>GF</th>
            <th>GC</th>
            <th>DG</th>
            <th>Pts</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
  }

  const html = `
    <div class="groups-grid">
      ${groups.map(g => renderGroupTable(g)).join('')}
    </div>
  `;
  container.innerHTML = html;
}

// ===== FIXTURE =====
async function loadFixture(phase) {
  const container = document.getElementById('fixtureContent');
  if (!container) return;
  container.innerHTML = '<div class="loading">Cargando partidos...</div>';
  try {
    const token = currentToken ? `Bearer ${currentToken}` : null;
    const data = await apiFetch(`/api/matches/?phase=${phase}`, {}, token);
    if (!data.phases || data.phases.length === 0) {
      container.innerHTML = '<p class="empty-state">Todavía no hay partidos cargados para esta fase. ¡Volvé pronto! ⚽</p>';
      return;
    }
    let html = '';
    for (const phaseGroup of data.phases) {
      if (phase !== 'group') {
        html += renderMatchList(phaseGroup.matches, phaseGroup.phase);
      } else {
        // Group phase: sort all matches chronologically, then group by day
        const allMatches = phaseGroup.matches.slice();
        allMatches.sort((a, b) => {
          if (!a.match_date) return 1;
          if (!b.match_date) return -1;
          return new Date(a.match_date) - new Date(b.match_date);
        });
        // Group by day
        const byDay = {};
        const dayOrder = [];
        for (const m of allMatches) {
          const dayKey = m.match_date
            ? new Date(m.match_date).toLocaleDateString('es-UY', { timeZone: 'America/Montevideo', year: 'numeric', month: '2-digit', day: '2-digit' })
            : 'Fecha a confirmar';
          if (!byDay[dayKey]) {
            byDay[dayKey] = [];
            dayOrder.push(dayKey);
          }
          byDay[dayKey].push(m);
        }
        for (const dayKey of dayOrder) {
          let dayLabel = dayKey;
          if (dayKey !== 'Fecha a confirmar') {
            try {
              // Parse dd/mm/yyyy back to a Date for formatting
              const [dd, mm, yyyy] = dayKey.split('/');
              const d = new Date(`${yyyy}-${mm}-${dd}T12:00:00`);
              dayLabel = d.toLocaleDateString('es-UY', {
                weekday: 'long', day: 'numeric', month: 'long', timeZone: 'America/Montevideo'
              });
              // Capitalize first letter
              dayLabel = dayLabel.charAt(0).toUpperCase() + dayLabel.slice(1);
            } catch {}
          }
          html += `<div class="group-label">${dayLabel}</div>`;
          html += renderMatchList(byDay[dayKey], 'group');
        }
      }
    }
    container.innerHTML = html || '<p class="empty-state">No hay partidos en esta fase aún.</p>';
  } catch (e) {
    container.innerHTML = '<p class="empty-state">Error cargando partidos. Intentá de nuevo.</p>';
  }
}
function renderMatchList(matches, phase) {
  return matches.map(m => renderMatchCard(m, phase)).join('');
}

function renderMatchCard(m, phase) {
  const homeTeam = m.home_team || {};
  const awayTeam = m.away_team || {};
  const homeName = homeTeam.name || m.home_team_placeholder || '?';
  const awayName = awayTeam.name || m.away_team_placeholder || '?';
  const homeFlag = teamFlagHtml(homeTeam);
  const awayFlag = teamFlagHtml(awayTeam);

  const isKnockout = ['r16','qf','sf','third','final'].includes(phase);
  const isFinished = m.status === 'finished';
  const isLive = m.status === 'live';
  const isLocked = m.predictions_locked;
  // Cierre 30 min antes del partido
  const matchDateF = m.match_date ? new Date(m.match_date) : null;
  const isClosed = isLocked || (matchDateF && Date.now() >= matchDateF.getTime() - 30 * 60 * 1000);

  // Date + venue
  const dateStr = m.match_date ? formatMatchDate(m.match_date) : 'Fecha a confirmar';
  const venueStr = (m.venue || m.city) ? ` · ${escHtml(m.venue || m.city)}` : '';
  const metaLine = dateStr + venueStr;

  // User prediction scores to display
  const pred = m.user_prediction;
  let homeScoreDisplay, awayScoreDisplay, predResultHtml = '';

  if (isFinished) {
    // Show actual result
    homeScoreDisplay = `<span class="mc-score-num result">${m.home_score}</span>`;
    awayScoreDisplay = `<span class="mc-score-num result">${m.away_score}</span>`;
    // Points badge
    if (pred && pred.points_calculated) {
      const pts = pred.points_earned;
      const label = pts === 10 ? '🎯 Exacto' : pts === 7 ? '✅ Empate OK' : pts === 5 ? '↔️ Diferencia' : pts === 3 ? '👍 Ganador' : '❌ Perdiste';
      const predStr = `${pred.predicted_home_score}-${pred.predicted_away_score}`;
      predResultHtml = `<div class="mc-pred-badge pts-${pts}">${label} <strong>${pts} pts</strong><br><small>Tu pronóstico: ${predStr}</small></div>`;
    }
  } else if (isLive) {
    homeScoreDisplay = `<span class="mc-score-num live">${m.home_score ?? '?'}</span>`;
    awayScoreDisplay = `<span class="mc-score-num live">${m.away_score ?? '?'}</span>`;
    // Show provisional points if we have a prediction and real scores
    if (pred && m.home_score != null && m.away_score != null) {
      const prov = pred.provisional_points;
      if (prov != null) {
        const provLabel = prov === 10 ? '🎯 Exacto' : prov === 7 ? '✅ Empate OK' : prov === 5 ? '↔️ Diferencia' : prov === 3 ? '👍 Ganador' : '❌ Sin puntos';
        predResultHtml = `<div class="mc-pred-badge pts-prov">⏱️ En vivo: ${provLabel} <strong>${prov} pts provisorios</strong></div>`;
      }
    }
  } else {
    // Upcoming: show user's predicted scores or "?"
    if (pred) {
      homeScoreDisplay = `<span class="mc-score-num predicted">${pred.predicted_home_score}</span>`;
      awayScoreDisplay = `<span class="mc-score-num predicted">${pred.predicted_away_score}</span>`;
    } else {
      homeScoreDisplay = `<span class="mc-score-num empty">?</span>`;
      awayScoreDisplay = `<span class="mc-score-num empty">?</span>`;
    }
  }

  // VS / live / result separator
  let centerSep;
  if (isLive) {
    centerSep = `<span class="mc-vs live-dot">🔴 EN VIVO</span>`;
  } else if (isFinished) {
    centerSep = `<span class="mc-vs finished">-</span>`;
  } else {
    centerSep = `<span class="mc-vs">VS</span>`;
  }

  // Action button
  let actionHtml = '';
  if (!isClosed && !isFinished && !isLive && currentUser) {
    const btnLabel = pred ? '✏️ Editar' : 'Pronosticar';
    const btnClass = pred ? 'mc-btn predicted' : 'mc-btn';
    actionHtml = `<button class="${btnClass}" onclick="openPredModal(${JSON.stringify(m).replace(/"/g, '&quot;')})">${btnLabel}</button>`;
  } else if (!currentUser && !isFinished && !isClosed && !isLive) {
    actionHtml = `<button class="mc-btn" onclick="navigate('register')">Registrate para pronosticar</button>`;
  
  } else if (isClosed && !isFinished && !isLive) {
    actionHtml = `<span class="match-closed-badge">🔒 Pronósticos cerrados</span>`;
  }

  // ET/PK note for finished KO matches
  let etNote = '';
  if (isFinished && isKnockout) {
    if (m.penalties) etNote = `<span class="mc-et-note">Penales</span>`;
    else if (m.extra_time) etNote = `<span class="mc-et-note">Tiempo extra</span>`;
  }

  const cardClass = `match-card-v2${isFinished ? ' finished' : ''}${isLive ? ' live' : ''}`;

  return `
    <div class="${cardClass}">
      <div class="mc-row">
        <div class="mc-team home">
          <span class="mc-flag">${homeFlag}</span>
          <span class="mc-name">${escHtml(homeName)}</span>
        </div>
        <div class="mc-scores">
          ${homeScoreDisplay}
          ${centerSep}
          ${awayScoreDisplay}
        </div>
        <div class="mc-team away">
          <span class="mc-flag">${awayFlag}</span>
          <span class="mc-name">${escHtml(awayName)}</span>
        </div>
      </div>
      <div class="mc-meta">${metaLine}${etNote}</div>
      ${predResultHtml}
      ${actionHtml ? `<div class="mc-action">${actionHtml}</div>` : ''}
    </div>
  `;
}


// ===== PREDICTION MODAL =====
function openPredModal(match) {
  currentMatchForPred = match;
  selectedKoWinner = null;

  const homeTeam = match.home_team || {};
  const awayTeam = match.away_team || {};
  const homeName = homeTeam.name || match.home_team_placeholder || '?';
  const awayName = awayTeam.name || match.away_team_placeholder || '?';
  const isKnockout = ['r16','qf','sf','third','final'].includes(match.phase);

  document.getElementById('modalTitle').textContent = 'Pronosticá este partido';
  document.getElementById('modalMatchInfo').textContent = match.match_date ? formatMatchDate(match.match_date) : '';
  document.getElementById('predHomeFlag').innerHTML = teamFlagHtml(homeTeam);
  document.getElementById('predHomeName').textContent = homeName;
  document.getElementById('predAwayFlag').innerHTML = teamFlagHtml(awayTeam);
  document.getElementById('predAwayName').textContent = awayName;
  document.getElementById('koWinnerHomeBtn').textContent = homeName;
  document.getElementById('koWinnerAwayBtn').textContent = awayName;

  // Load existing prediction
  const pred = match.user_prediction;
  const homeVal = pred ? pred.predicted_home_score : 0;
  const awayVal = pred ? pred.predicted_away_score : 0;
  const homeEl2 = document.getElementById('predHomeScore');
  const awayEl2 = document.getElementById('predAwayScore');
  if (homeEl2) { homeEl2.dataset.value = homeVal; homeEl2.textContent = homeVal; }
  if (awayEl2) { awayEl2.dataset.value = awayVal; awayEl2.textContent = awayVal; }

  // Knockout options
  const koSection = document.getElementById('knockoutOptions');
  koSection.style.display = isKnockout ? 'block' : 'none';

  if (isKnockout) {
    setupKnockoutListeners();
    if (pred) {
      checkKnockoutDraw();
    }
  }

  document.getElementById('predError').style.display = 'none';
  document.getElementById('predModal').style.display = 'flex';
}

function setupKnockoutListeners() {
  const homeScore = document.getElementById('predHomeScore');
  const awayScore = document.getElementById('predAwayScore');
  homeScore.addEventListener('input', checkKnockoutDraw);
  awayScore.addEventListener('input', checkKnockoutDraw);
}

function checkKnockoutDraw() {
  const h = parseInt(document.getElementById('predHomeScore').value) || 0;
  const a = parseInt(document.getElementById('predAwayScore').value) || 0;
  const isDraw = h === a;
  document.getElementById('koResolveSection').style.display = isDraw ? 'block' : 'none';
  if (!isDraw) {
    // Reset all KO state when score becomes non-draw
    selectedKoWinner = null;
    document.getElementById('koWinnerSection').style.display = 'none';
    document.getElementById('koWinnerHomeBtn').classList.remove('selected');
    document.getElementById('koWinnerAwayBtn').classList.remove('selected');
    document.querySelectorAll('input[name="resolve"]').forEach(r => r.checked = false);
  }
}

// Called when ET or PK radio changes — show the winner selector with correct label
function onResolveChange() {
  const resolveVal = document.querySelector('input[name="resolve"]:checked')?.value;
  const winnerSection = document.getElementById('koWinnerSection');
  const label = document.getElementById('koWinnerLabel');
  if (resolveVal === 'et') {
    label.textContent = '¿Quién gana en tiempo extra?';
    winnerSection.style.display = 'block';
  } else if (resolveVal === 'pk') {
    label.textContent = '¿Quién gana en penales?';
    winnerSection.style.display = 'block';
  } else {
    winnerSection.style.display = 'none';
  }
  // Reset winner selection when resolution type changes
  selectedKoWinner = null;
  document.getElementById('koWinnerHomeBtn').classList.remove('selected');
  document.getElementById('koWinnerAwayBtn').classList.remove('selected');
}

// Called when user picks the winning team
function setKoWinner(side) {
  selectedKoWinner = side === 'home'
    ? currentMatchForPred?.home_team?.id
    : currentMatchForPred?.away_team?.id;
  document.getElementById('koWinnerHomeBtn').classList.toggle('selected', side === 'home');
  document.getElementById('koWinnerAwayBtn').classList.toggle('selected', side === 'away');
}

function closePredModal() {
  document.getElementById('predModal').style.display = 'none';
  currentMatchForPred = null;
  selectedKoWinner = null;
}

async function submitPrediction(e) {
  e.preventDefault();
  if (!currentUser) { navigate('login'); return; }

  const match = currentMatchForPred;
  const isKnockout = ['r16','qf','sf','third','final'].includes(match.phase);
  const homeEl = document.getElementById('predHomeScore');
  const awayEl = document.getElementById('predAwayScore');
  const homeScore = parseInt(homeEl.dataset ? homeEl.dataset.value : homeEl.value) || 0;
  const awayScore = parseInt(awayEl.dataset ? awayEl.dataset.value : awayEl.value) || 0;
  const isDraw = homeScore === awayScore;

  let extraTime = false;
  let penalties = false;
  let penaltyWinnerId = null;
  let etWinnerId = null;

  if (isKnockout && isDraw) {
    const resolveVal = document.querySelector('input[name="resolve"]:checked')?.value;
    if (!resolveVal) {
      showPredError('Indicá si se resuelve por tiempo extra o penales');
      return;
    }
    if (!selectedKoWinner) {
      showPredError(resolveVal === 'pk' ? 'Indicá qué equipo gana los penales' : 'Indicá qué equipo gana en tiempo extra');
      return;
    }
    extraTime = true;
    penalties = resolveVal === 'pk';
    if (penalties) {
      penaltyWinnerId = selectedKoWinner;
    } else {
      etWinnerId = selectedKoWinner;
    }
  }

  const btn = document.getElementById('predBtn');
  btn.textContent = 'Guardando...';
  btn.disabled = true;

  try {
    await apiFetch('/api/predictions/', {
      method: 'POST',
      body: JSON.stringify({
        match_id: match.id,
        predicted_home_score: homeScore,
        predicted_away_score: awayScore,
        predicted_extra_time: extraTime,
        predicted_penalties: penalties,
        predicted_penalty_winner_id: penaltyWinnerId,
        predicted_et_winner_id: etWinnerId
      })
    }, `Bearer ${currentToken}`);

    closePredModal();
    showToast('¡Pronóstico guardado! ⚽', 'success');
    loadFixture(currentPhase);
  } catch (err) {
    showPredError(err.message || 'Error al guardar el pronóstico');
  } finally {
    btn.textContent = 'GUARDAR PRONÓSTICO';
    btn.disabled = false;
  }
}

function showPredError(msg) {
  const el = document.getElementById('predError');
  el.textContent = msg;
  el.style.display = 'block';
}

// ===== RANKING =====
async function loadRanking() {
  const container = document.getElementById('rankingContent');
  if (!container) return;
  container.innerHTML = '<div class="loading">Cargando ranking...</div>';

  try {
    const token = currentToken ? `Bearer ${currentToken}` : null;
    const data = await apiFetch('/api/ranking/?limit=100', {}, token);

    // User banner
    const banner = document.getElementById('userRankBanner');
    if (data.user_position && currentUser) {
      const pos = data.user_position;
      banner.style.display = 'flex';
      banner.innerHTML = `
        <div>
          <strong style="font-family:var(--font-display);font-size:1.2rem;letter-spacing:1px">TU POSICIÓN</strong><br>
          <span style="color:var(--gray);font-size:0.85rem">${escHtml(pos.username)}</span>
        </div>
        <div style="text-align:right">
          <div style="font-family:var(--font-display);font-size:2rem;color:var(--gold)">#${pos.position}</div>
          <div style="font-size:0.8rem;color:#aaa">${pos.total_points} puntos</div>
        </div>
      `;
    } else {
      banner.style.display = 'none';
    }

    if (!data.ranking || data.ranking.length === 0) {
      container.innerHTML = '<p class="empty-state">El ranking estará disponible cuando empiece el mundial 🏆</p>';
      return;
    }

    const medals = { 1: '🥇', 2: '🥈', 3: '🥉' };
    const posClass = { 1: 'gold', 2: 'silver', 3: 'bronze' };

    const rows = data.ranking.map(u => {
      const isMe = currentUser && u.id === currentUser.id;
      const pos = u.position;
      const medal = medals[pos] || pos;
      const cls = posClass[pos] || '';
      return `
        <tr class="${isMe ? 'rank-highlight' : ''}" data-username="${escHtml(u.username)}" style="cursor:pointer" onclick="navigate('rival', this.dataset.username)" title="Ver pronósticos de ${escHtml(u.username)}">
          <td><span class="rank-pos ${cls}">${medal}</span></td>
          <td>
            <div class="rank-username">${escHtml(u.username)}${isMe ? ' <small style="color:var(--gold)">← vos</small>' : ''}</div>
            ${u.full_name ? `<div style="font-size:0.75rem;color:var(--gray)">${escHtml(u.full_name)}</div>` : ''}
          </td>
          <td style="font-size:0.85rem;color:var(--gold);font-weight:700;text-align:center">${u.exact_results || 0}</td>
          <td>
            ${u.provisional_total != null && u.provisional_total !== u.total_points
              ? `<div class="rank-points">${u.provisional_total} <span style="font-size:0.65rem;color:var(--gray)">⏱️</span></div>`
              : `<div class="rank-points">${u.total_points}</div>`
            }
          </td>
        </tr>
      `;
    }).join('');

    container.innerHTML = `
      <table class="ranking-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Jugador</th>
            <th>🎯 Exactos</th>
            <th>Puntos</th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>
    `;
  } catch {
    container.innerHTML = '<p class="empty-state">Error cargando el ranking.</p>';
  }
}

// ===== PROFILE =====
async function loadProfile() {
  if (!currentUser) { navigate('login'); return; }
  const container = document.getElementById('profileContent');
  container.innerHTML = '<div class="loading">Cargando...</div>';

  try {
    const [profile, stats] = await Promise.all([
      apiFetch('/api/auth/profile', {}, `Bearer ${currentToken}`),
      apiFetch('/api/predictions/stats', {}, `Bearer ${currentToken}`)
    ]);

    container.innerHTML = `
      <div class="profile-grid">
        <div class="profile-card">
          <h3>👤 MIS DATOS</h3>
          <div class="profile-stat">
            <span>Usuario</span>
            <span><strong>${escHtml(profile.username)}</strong></span>
          </div>
          <div class="profile-stat">
            <span>Email</span>
            <span>${escHtml(profile.email)}</span>
          </div>
          ${profile.full_name ? `
          <div class="profile-stat">
            <span>Nombre</span>
            <span>${escHtml(profile.full_name)}</span>
          </div>` : ''}
          <div class="profile-stat">
            <span>Participando desde</span>
            <span>${formatDate(profile.created_at)}</span>
          </div>
        </div>

        <div class="profile-card">
          <h3>🏆 MIS PUNTOS</h3>
          <div class="profile-stat">
            <span>Total</span>
            <span class="profile-stat-val" style="color:var(--gold)">${profile.total_points} pts</span>
          </div>
          <div class="profile-stat">
            <span>⚽ Por pronósticos</span>
            <span class="profile-stat-val">${profile.prediction_points}</span>
          </div>
          <div class="profile-stat">
            <span>🛍️ Por compras TUYA</span>
            <span class="profile-stat-val" style="color:var(--green)">${profile.purchase_points}</span>
          </div>
        </div>

        <div class="profile-card">
          <h3>📊 MIS ESTADÍSTICAS</h3>
          <div class="profile-stat">
            <span>Pronósticos realizados</span>
            <span class="profile-stat-val">${stats.total_predictions}</span>
          </div>
          <div class="profile-stat">
            <span>🎯 Exactos (10 pts)</span>
            <span class="profile-stat-val" style="color:var(--gold)">${stats.exact_results}</span>
          </div>
          <div class="profile-stat">
            <span>✅ Empate OK (7 pts)</span>
            <span class="profile-stat-val" style="color:var(--green)">${stats.exact_draws}</span>
          </div>
          <div class="profile-stat">
            <span>↔️ Diferencia exacta (5 pts)</span>
            <span class="profile-stat-val" style="color:var(--blue)">${stats.exact_differences}</span>
          </div>
          <div class="profile-stat">
            <span>👍 Ganador correcto (3 pts)</span>
            <span class="profile-stat-val" style="color:var(--orange)">${stats.correct_winners}</span>
          </div>
          <div class="profile-stat">
            <span>❌ Errados</span>
            <span class="profile-stat-val" style="color:var(--gray)">${stats.misses}</span>
          </div>
        </div>

        <div class="profile-card">
          <h3>💡 SUMÁ MÁS PUNTOS</h3>
          <p style="color:var(--gray);font-size:0.9rem;margin-bottom:1rem">Cada compra en TUYA te suma <strong>10 puntos extra</strong> — igual que pronosticar el resultado exacto.</p>
          <p style="color:var(--gray);font-size:0.85rem;margin-bottom:1.5rem">Usá el mismo email con el que te registraste acá: <strong>${escHtml(profile.email)}</strong></p>
          <a href="https://tuyauy.com" target="_blank" class="btn-primary dark" style="display:block;text-align:center;text-decoration:none;padding:0.75rem">
            IR A TUYAUY.COM ↗
          </a>
        </div>
      </div>

      <div style="margin-top:1rem;padding-bottom:3rem">
        <h3 style="font-family:var(--font-display);font-size:1.2rem;letter-spacing:1px;margin-bottom:1rem">MIS PRONÓSTICOS</h3>
        <div id="myPredictions"><div class="loading">Cargando...</div></div>
      </div>
    `;

    loadMyPredictions();
  } catch (e) {
    container.innerHTML = '<p class="empty-state">Error cargando tu perfil.</p>';
  }
}

async function loadMyPredictions() {
  const container = document.getElementById('myPredictions');
  if (!container) return;
  try {
    const preds = await apiFetch('/api/predictions/my', {}, `Bearer ${currentToken}`);
    if (!preds || preds.length === 0) {
      container.innerHTML = '<p class="empty-state">Todavía no hiciste pronósticos. <a href="#" onclick="navigate(\'fixture\')">¡Ir al fixture!</a></p>';
      return;
    }
    container.innerHTML = preds.map(p => {
      const m = p.match;
      const homeName = (m?.home_team?.name) || m?.home_team_placeholder || '?';
      const awayName = (m?.away_team?.name) || m?.away_team_placeholder || '?';
      const predStr = `${p.predicted_home_score}-${p.predicted_away_score}`;
      const resultStr = m?.status === 'finished' ? `${m.home_score}-${m.away_score}` : '-';
      let ptsBadge = '';
      if (p.points_calculated) {
        const pts = p.points_earned;
        const color = pts===10?'var(--gold)':pts===7?'var(--green)':pts===5?'var(--blue)':pts===3?'var(--orange)':'var(--red)';
        ptsBadge = `<strong style="color:${color}">${pts} pts</strong>`;
      }
      return `
        <div class="match-card" style="margin-bottom:0.5rem">
          <div style="font-size:0.9rem"><strong>${escHtml(homeName)}</strong> vs <strong>${escHtml(awayName)}</strong></div>
          <div style="text-align:center">
            <div style="font-size:0.8rem;color:var(--gray)">Tu pronóstico: <strong>${predStr}</strong></div>
            ${resultStr !== '-' ? `<div style="font-size:0.8rem;color:var(--gray)">Resultado: <strong>${resultStr}</strong></div>` : ''}
            ${ptsBadge}
          </div>
          <div style="font-size:0.75rem;color:var(--gray)">${m?.match_date ? formatMatchDate(m.match_date) : ''}</div>
        </div>
      `;
    }).join('');
  } catch {
    container.innerHTML = '<p class="empty-state">Error cargando pronósticos.</p>';
  }
}

// ===== ADMIN PANEL =====
async function loadAdmin() {
  if (!currentUser?.is_admin) {
    document.getElementById('adminContent').innerHTML = '<p class="empty-state">Acceso denegado.</p>';
    return;
  }
  const container = document.getElementById('adminContent');
  container.innerHTML = '<div class="loading">Cargando panel...</div>';

  try {
    const stats = await apiFetch('/api/admin/stats', {}, `Bearer ${currentToken}`);

    container.innerHTML = `
      <div class="admin-grid">
        <!-- Stats -->
        <div class="admin-card">
          <h3>📊 ESTADÍSTICAS</h3>
          <div class="profile-stat"><span>Participantes</span><strong>${stats.total_users}</strong></div>
          <div class="profile-stat"><span>Pronósticos</span><strong>${stats.total_predictions}</strong></div>
          <div class="profile-stat"><span>Partidos jugados</span><strong>${stats.matches_finished}</strong></div>
          <div class="profile-stat"><span>Partidos pendientes</span><strong>${stats.matches_pending}</strong></div>
          <div class="profile-stat"><span>Compras registradas</span><strong>${stats.total_purchases_registered}</strong></div>
        </div>

        <!-- Cargar resultado -->
        <div class="admin-card">
          <h3>⚽ CARGAR RESULTADO</h3>
          <div class="form-group">
            <label>ID del partido</label>
            <input type="number" id="adminMatchId" placeholder="Ej: 1" />
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
            <div class="form-group">
              <label>Goles Local</label>
              <input type="number" id="adminHomeScore" min="0" value="0" />
            </div>
            <div class="form-group">
              <label>Goles Visitante</label>
              <input type="number" id="adminAwayScore" min="0" value="0" />
            </div>
          </div>
          <div class="form-group">
            <label style="display:flex;align-items:center;gap:0.5rem;cursor:pointer">
              <input type="checkbox" id="adminET" onchange="toggleAdminET()" /> Hubo tiempo extra
            </label>
          </div>
          <div id="adminPenSection" style="display:none" class="form-group">
            <label style="display:flex;align-items:center;gap:0.5rem;cursor:pointer">
              <input type="checkbox" id="adminPK" onchange="toggleAdminPK()" /> Hubo penales
            </label>
          </div>
          <div id="adminPKWinner" style="display:none" class="form-group">
            <label>ID equipo ganador en penales</label>
            <input type="number" id="adminPKWinnerId" placeholder="ID del equipo" />
          </div>
          <button class="btn-primary dark" onclick="submitAdminResult()" style="width:100%">CARGAR RESULTADO</button>
          <div id="adminResultMsg" style="margin-top:0.5rem;font-size:0.85rem"></div>
        </div>

        <!-- Puntos por compra -->
        <div class="admin-card">
          <h3>🛍️ PUNTOS POR COMPRA</h3>
          <p style="color:var(--gray);font-size:0.85rem;margin-bottom:1rem">Registrá manualmente una compra para otorgar puntos.</p>
          <div class="form-group">
            <label>Email del cliente</label>
            <input type="email" id="adminPurchaseEmail" placeholder="cliente@email.com" />
          </div>
          <div class="form-group">
            <label>Número de orden (opcional)</label>
            <input type="text" id="adminOrderId" placeholder="Ej: ORD-12345" />
          </div>
          <div class="form-group">
            <label>Monto de la compra (opcional)</label>
            <input type="number" id="adminOrderAmount" placeholder="Ej: 2500" />
          </div>
          <button class="btn-primary dark" onclick="submitAdminPurchase()" style="width:100%">OTORGAR 10 PUNTOS</button>
          <div id="adminPurchaseMsg" style="margin-top:0.5rem;font-size:0.85rem"></div>
        </div>

        <!-- Bloquear partido -->
        <div class="admin-card">
          <h3>🔒 BLOQUEAR PARTIDO</h3>
          <p style="color:var(--gray);font-size:0.85rem;margin-bottom:1rem">Bloqueá las predicciones cuando empiece el partido.</p>
          <div class="form-group">
            <label>ID del partido</label>
            <input type="number" id="adminLockMatchId" placeholder="Ej: 1" />
          </div>
          <button class="btn-primary dark" onclick="submitAdminLock()" style="width:100%">BLOQUEAR</button>
          <div id="adminLockMsg" style="margin-top:0.5rem;font-size:0.85rem"></div>
        </div>
      </div>

      <!-- Matches list -->
      <div style="margin-top:2rem;padding-bottom:3rem">
        <h3 style="font-family:var(--font-display);font-size:1.3rem;letter-spacing:1px;margin-bottom:1rem">PARTIDOS CARGADOS</h3>
        <div id="adminMatchesList"><div class="loading">Cargando...</div></div>
      </div>
    `;

    loadAdminMatches();
  } catch {
    container.innerHTML = '<p class="empty-state">Error cargando el panel de admin.</p>';
  }
}

function toggleAdminET() {
  const checked = document.getElementById('adminET').checked;
  document.getElementById('adminPenSection').style.display = checked ? 'block' : 'none';
  if (!checked) {
    document.getElementById('adminPKWinner').style.display = 'none';
    document.getElementById('adminPK').checked = false;
  }
}

function toggleAdminPK() {
  const checked = document.getElementById('adminPK').checked;
  document.getElementById('adminPKWinner').style.display = checked ? 'block' : 'none';
}

async function submitAdminResult() {
  const matchId = document.getElementById('adminMatchId').value;
  const homeScore = parseInt(document.getElementById('adminHomeScore').value) || 0;
  const awayScore = parseInt(document.getElementById('adminAwayScore').value) || 0;
  const extraTime = document.getElementById('adminET').checked;
  const penalties = document.getElementById('adminPK')?.checked || false;
  const penaltyWinnerId = document.getElementById('adminPKWinnerId')?.value || null;

  if (!matchId) { showAdminMsg('adminResultMsg', 'Ingresá el ID del partido', 'error'); return; }

  try {
    const res = await apiFetch(`/api/admin/matches/${matchId}/result`, {
      method: 'POST',
      body: JSON.stringify({
        home_score: homeScore,
        away_score: awayScore,
        extra_time: extraTime,
        penalties: penalties,
        penalty_winner_id: penaltyWinnerId ? parseInt(penaltyWinnerId) : null
      })
    }, `Bearer ${currentToken}`);
    showAdminMsg('adminResultMsg', res.message, 'success');
    loadAdminMatches();
  } catch (e) {
    showAdminMsg('adminResultMsg', e.message, 'error');
  }
}

async function submitAdminPurchase() {
  const email = document.getElementById('adminPurchaseEmail').value.trim();
  const orderId = document.getElementById('adminOrderId').value.trim();
  const amount = document.getElementById('adminOrderAmount').value;

  if (!email) { showAdminMsg('adminPurchaseMsg', 'Ingresá el email', 'error'); return; }

  try {
    const res = await apiFetch('/api/purchases/grant', {
      method: 'POST',
      body: JSON.stringify({
        email,
        order_id: orderId || null,
        order_amount: amount ? parseFloat(amount) : null
      })
    }, `Bearer ${currentToken}`);
    showAdminMsg('adminPurchaseMsg', res.message, 'success');
    document.getElementById('adminPurchaseEmail').value = '';
    document.getElementById('adminOrderId').value = '';
    document.getElementById('adminOrderAmount').value = '';
  } catch (e) {
    showAdminMsg('adminPurchaseMsg', e.message, 'error');
  }
}

async function submitAdminLock() {
  const matchId = document.getElementById('adminLockMatchId').value;
  if (!matchId) { showAdminMsg('adminLockMsg', 'Ingresá el ID del partido', 'error'); return; }
  try {
    await apiFetch(`/api/admin/matches/${matchId}/lock`, {
      method: 'POST'
    }, `Bearer ${currentToken}`);
    showAdminMsg('adminLockMsg', 'Partido bloqueado correctamente', 'success');
    loadAdminMatches();
  } catch (e) {
    showAdminMsg('adminLockMsg', e.message, 'error');
  }
}

async function loadAdminMatches() {
  const container = document.getElementById('adminMatchesList');
  if (!container) return;
  try {
    const matches = await apiFetch('/api/admin/matches', {}, `Bearer ${currentToken}`);
    if (!matches || matches.length === 0) {
      container.innerHTML = '<p class="empty-state">No hay partidos cargados aún.</p>';
      return;
    }
    container.innerHTML = `
      <table class="ranking-table">
        <thead>
          <tr>
            <th>ID</th><th>Fase</th><th>Local</th><th>Visitante</th><th>Fecha</th><th>Estado</th><th>Resultado</th>
          </tr>
        </thead>
        <tbody>
          ${matches.map(m => `
            <tr>
              <td><strong>#${m.id}</strong></td>
              <td>${m.phase}</td>
              <td>${m.home_team?.name || m.home_team_placeholder || '-'}</td>
              <td>${m.away_team?.name || m.away_team_placeholder || '-'}</td>
              <td>${m.match_date ? formatMatchDate(m.match_date) : '-'}</td>
              <td><span class="match-status-badge ${m.status}">${m.status}</span></td>
              <td>${m.status === 'finished' ? `${m.home_score}-${m.away_score}` : '-'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  } catch {
    container.innerHTML = '<p class="empty-state">Error cargando partidos.</p>';
  }
}

function showAdminMsg(elId, msg, type) {
  const el = document.getElementById(elId);
  if (!el) return;
  el.textContent = msg;
  el.style.color = type === 'error' ? 'var(--red)' : 'var(--green)';
}

// ===== AUTH HANDLERS =====
async function handleRegister(e) {
  e.preventDefault();
  const btn = document.getElementById('registerBtn');
  const errEl = document.getElementById('registerError');
  errEl.style.display = 'none';

  btn.textContent = 'Registrando...';
  btn.disabled = true;

  try {
    const data = await apiFetch('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({
        email: document.getElementById('regEmail').value,
        username: document.getElementById('regUsername').value,
        password: document.getElementById('regPassword').value,
        full_name: document.getElementById('regName').value || null
      })
    });

    localStorage.setItem('penca_token', data.token);
    localStorage.setItem('penca_user', JSON.stringify(data.user));
    currentToken = data.token;
    currentUser = data.user;
    renderNavAuth();
    showToast('¡Bienvenido a la Penca TUYA! ⚽', 'success');
    navigate('fixture');
  } catch (err) {
    errEl.textContent = err.message || 'Error al registrarse';
    errEl.style.display = 'block';
  } finally {
    btn.textContent = 'UNIRME A LA PENCA';
    btn.disabled = false;
  }
}

async function handleLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('loginBtn');
  const errEl = document.getElementById('loginError');
  errEl.style.display = 'none';

  btn.textContent = 'Entrando...';
  btn.disabled = true;

  try {
    const data = await apiFetch('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        email: document.getElementById('loginEmail').value,
        password: document.getElementById('loginPassword').value
      })
    });

    localStorage.setItem('penca_token', data.token);
    localStorage.setItem('penca_user', JSON.stringify(data.user));
    currentToken = data.token;
    currentUser = data.user;
    renderNavAuth();
    showToast('¡Bienvenido de vuelta! ⚽', 'success');
    navigate('fixture');
  } catch (err) {
    errEl.textContent = err.message || 'Email o contraseña incorrectos';
    errEl.style.display = 'block';
  } finally {
    btn.textContent = 'ENTRAR';
    btn.disabled = false;
  }
}

// ===== API HELPER =====
async function apiFetch(path, options = {}, authHeader = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (authHeader) headers['Authorization'] = authHeader;

  const res = await fetch(`${API}${path}`, {
    headers,
    ...options
  });

  let data;
  try { data = (await res.json()) ?? {}; } catch { data = {}; }

  if (!res.ok) {
    const msg = data?.detail || data?.message || `Error ${res.status}`;
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }

  return data;
}

// ===== UTILITIES =====
function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatMatchDate(isoStr) {
  try {
    const d = new Date(isoStr);
    const TZ = 'America/Montevideo';
    // Date part: "Jue 12 jun"
    const datePart = d.toLocaleDateString('es-UY', {
      weekday: 'short', day: 'numeric', month: 'short', timeZone: TZ
    });
    // Time part: "19:00"
    const timePart = d.toLocaleTimeString('es-UY', {
      hour: '2-digit', minute: '2-digit', hour12: false, timeZone: TZ
    });
    // Capitalize weekday first letter
    const formatted = datePart.charAt(0).toUpperCase() + datePart.slice(1);
    return `${formatted} · ${timePart}`;
  } catch { return isoStr; }
}

function formatDate(isoStr) {
  try {
    const d = new Date(isoStr);
    return d.toLocaleDateString('es-UY', { day: 'numeric', month: 'long', year: 'numeric' });
  } catch { return isoStr; }
}

function teamFlagHtml(team) {
  if (!team) return '🏳️';
  if (team.flag_url) {
    return `<img src="${team.flag_url}" alt="${escHtml(team.name || '')}" class="team-flag-img" onerror="this.replaceWith(document.createTextNode('${teamFlag(team.code)}'))" />`;
  }
  return teamFlag(team.code);
}

function teamFlag(code) {
  if (!code) return '🏳️';
  const flags = {
    'USA': '🇺🇸', 'MEX': '🇲🇽', 'PAN': '🇵🇦', 'HON': '🇭🇳',
    'ARG': '🇦🇷', 'ECU': '🇪🇨', 'VEN': '🇻🇪', 'JAM': '🇯🇲',
    'FRA': '🇫🇷', 'GER': '🇩🇪', 'POR': '🇵🇹', 'GEO': '🇬🇪',
    'ESP': '🇪🇸', 'CRO': '🇭🇷', 'SRB': '🇷🇸', 'SVK': '🇸🇰',
    'BRA': '🇧🇷', 'URU': '🇺🇾', 'COL': '🇨🇴', 'BOL': '🇧🇴',
    'ENG': '🏴󠁧󠁢󠁥󠁮󠁧󠁿', 'NED': '🇳🇱', 'BEL': '🇧🇪', 'SCO': '🏴󠁧󠁢󠁳󠁣󠁴󠁿',
    'MAR': '🇲🇦', 'SEN': '🇸🇳', 'MLI': '🇲🇱', 'RSA': '🇿🇦',
    'JPN': '🇯🇵', 'AUS': '🇦🇺', 'KSA': '🇸🇦', 'UZB': '🇺🇿',
    'TUR': '🇹🇷', 'CZE': '🇨🇿', 'ALB': '🇦🇱', 'POL': '🇵🇱',
    'ROU': '🇷🇴', 'AUT': '🇦🇹', 'HUN': '🇭🇺', 'KOR': '🇰🇷',
    'IRN': '🇮🇷', 'IRQ': '🇮🇶', 'OMA': '🇴🇲', 'CAN': '🇨🇦',
    'CRC': '🇨🇷', 'SLV': '🇸🇻', 'TRI': '🇹🇹'
  };
  return flags[code] || '🏳️';
}

function showToast(msg, type = '') {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = `toast ${type}`;
  toast.style.display = 'block';
  setTimeout(() => { toast.style.display = 'none'; }, 3000);
}


// ===== FORGOT / RESET PASSWORD =====
async function submitForgotPassword() {
  const btn = document.getElementById('forgotBtn');
  const errEl = document.getElementById('forgotError');
  const email = document.getElementById('forgotEmail').value.trim();
  if (!email) { errEl.style.display = 'block'; errEl.textContent = 'Ingresa tu email'; return; }
  btn.disabled = true;
  btn.textContent = 'Enviando...';
  errEl.textContent = '';
  errEl.style.display = 'none';
  try {
    const data = await apiFetch('/api/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email })
    });
    errEl.style.display = 'block';
    errEl.style.color = '#22c55e';
    errEl.style.background = 'rgba(34,197,94,0.1)';
    errEl.style.borderColor = 'rgba(34,197,94,0.3)';
    errEl.textContent = (data && data.message) ? data.message : 'Si ese email esta registrado, recibiras un link en breve.';
    btn.textContent = 'Enviado';
  } catch (e) {
    errEl.style.display = 'block';
    errEl.style.color = '';
    errEl.style.background = '';
    errEl.style.borderColor = '';
    errEl.textContent = e.message || 'Error al enviar. Intenta de nuevo.';
    btn.disabled = false;
    btn.textContent = 'Enviar link';
  }
}

async function submitResetPassword() {
  const btn = document.getElementById('resetBtn');
  const errEl = document.getElementById('resetError');
  const token = document.getElementById('resetToken').value.trim();
  const newPassword = document.getElementById('resetNewPassword').value;
  const confirmPassword = document.getElementById('resetConfirmPassword').value;
  if (newPassword !== confirmPassword) { errEl.style.display = 'block'; errEl.textContent = 'Las contrasenas no coinciden'; return; }
  if (newPassword.length < 6) { errEl.style.display = 'block'; errEl.textContent = 'La contrasena debe tener al menos 6 caracteres'; return; }
  btn.disabled = true;
  btn.textContent = 'Guardando...';
  errEl.textContent = '';
  errEl.style.display = 'none';
  try {
    const data = await apiFetch('/api/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword })
    });
    errEl.style.display = 'block';
    errEl.style.color = '#22c55e';
    errEl.style.background = 'rgba(34,197,94,0.1)';
    errEl.style.borderColor = 'rgba(34,197,94,0.3)';
    errEl.textContent = data.message;
    btn.textContent = 'Listo';
    setTimeout(() => navigate('login'), 2000);
  } catch (e) {
    errEl.style.display = 'block';
    errEl.style.color = '';
    errEl.style.background = '';
    errEl.style.borderColor = '';
    errEl.textContent = e.message || 'Error. El link puede haber expirado.';
    btn.disabled = false;
    btn.textContent = 'Cambiar contrasena';
  }
}


// ===== RIVAL PROFILE =====
async function loadRivalProfile(username) {
  if (!username) return;
  const headerEl = document.getElementById('rivalHeader');
  const listEl = document.getElementById('rivalPredictions');
  if (!headerEl || !listEl) return;

  headerEl.innerHTML = '<div class="loading">Cargando...</div>';
  listEl.innerHTML = '';

  try {
    const data = await apiFetch(`/api/predictions/users/${encodeURIComponent(username)}/predictions`);
    const user = data.user || {};
    const preds = data.predictions || [];

    headerEl.innerHTML = `
      <div class="rival-user-info">
        <h1 class="page-title">${escHtml(user.username || username)}</h1>
        <div class="rival-pts-badge">${user.total_points ?? 0} puntos</div>
      </div>
    `;

    if (preds.length === 0) {
      listEl.innerHTML = '<p class="empty-state">Todavía no hay partidos jugados para mostrar los pronósticos de este jugador.</p>';
      return;
    }

    listEl.innerHTML = preds.map(p => {
      const m = p.match || {};
      const ht = m.home_team || {};
      const at = m.away_team || {};
      const homeName = ht.name || m.home_team_placeholder || '?';
      const awayName = at.name || m.away_team_placeholder || '?';
      const homeFlag = ht.flag_url ? `<img src="${escHtml(ht.flag_url)}" class="rival-flag" alt="">` : '';
      const awayFlag = at.flag_url ? `<img src="${escHtml(at.flag_url)}" class="rival-flag" alt="">` : '';

      const predStr = `${p.predicted_home_score ?? '?'} - ${p.predicted_away_score ?? '?'}`;
      const finished = m.status === 'finished';
      const resultStr = finished ? `${m.home_score} - ${m.away_score}` : null;

      const pts = p.points_earned;
      let ptsBadge = '';
      if (pts != null) {
        const col = pts===10?'var(--gold)':pts===7?'var(--green)':pts===5?'var(--blue)':pts===3?'var(--orange)':'var(--red)';
        const label = pts===10?'⚽ Exacto':pts===7?'✅ Empate OK':pts===5?'↔️ Dif. exacta':pts===3?'👍 Ganador':'❌ Errado';
        ptsBadge = `<div class="rival-pts" style="color:${col}">${pts} pts <small>${label}</small></div>`;
      }

      return `
        <div class="rival-pred-card">
          <div class="rival-match-date">${m.match_date ? formatMatchDate(m.match_date) : ''}</div>
          <div class="rival-teams">
            <div class="rival-team home">${homeFlag}<span>${escHtml(homeName)}</span></div>
            <div class="rival-scores">
              <div class="rival-pred-score">${predStr}</div>
              ${resultStr ? `<div class="rival-real-score">${resultStr}</div>` : '<div class="rival-real-score pending">En juego</div>'}
              <div class="rival-score-labels">
                <span>pronóstico</span>
                <span>resultado</span>
              </div>
            </div>
            <div class="rival-team away">${awayFlag}<span>${escHtml(awayName)}</span></div>
          </div>
          ${ptsBadge}
        </div>
      `;
    }).join('');

  } catch(e) {
    headerEl.innerHTML = '<p class="empty-state">Error cargando el perfil.</p>';
    listEl.innerHTML = '';
  }
}
