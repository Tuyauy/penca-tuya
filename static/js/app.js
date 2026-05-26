/* =============================================
   PENCA TUYA MUNDIAL 2026 - App JS
   ============================================= */

const API = '';  // same origin

// ===== STATE =====
let currentUser = null;
let currentToken = null;
let currentPhase = 'group';
let currentMatchForPred = null;
let selectedPenaltyWinner = null;

// ===== INIT =====
document.addEventListener('DOMContentLoaded', () => {
  loadAuth();
  loadHomeStats();
  loadTop3();

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
  if (fullHash.startsWith('reset-password')) { const token = new URLSearchParams(fullHash.split('?')[1] || '').get('token'); if (token) { const el = document.getElementById('resetToken'); if (el) el.value = token; } }
  navigate(hash);
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
function navigate(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const target = document.getElementById(`page-${page}`);
  if (target) {
    target.classList.add('active');
    window.scrollTo(0, 0);
    window.location.hash = page;
  }

  // Load page data
  if (page === 'fixture') loadFixture(currentPhase);
  if (page === 'ranking') loadRanking();
  if (page === 'profile') loadProfile();
  if (page === 'admin') loadAdmin();
  if (page === 'prizes') {} // static
}

function toggleMenu() {
  const links = document.getElementById('navLinks');
  links.classList.toggle('open');
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
        // Group by group_name
        const byGroup = {};
        for (const m of phaseGroup.matches) {
          const g = m.group_name || '?';
          if (!byGroup[g]) byGroup[g] = [];
          byGroup[g].push(m);
        }
        for (const [g, matches] of Object.entries(byGroup).sort()) {
          html += `<div class="group-label">Grupo ${g}</div>`;
          html += renderMatchList(matches, 'group');
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

  // Score display
  let scoreHtml = '';
  if (isFinished) {
    let scoreStr = `${m.home_score} - ${m.away_score}`;
    if (m.extra_time) scoreStr += ' <small style="color:var(--gray)">PE</small>';
    if (m.penalties) scoreStr += ' <small style="color:var(--gray)">PEN</small>';
    scoreHtml = `<div class="match-score">${scoreStr}</div>`;
  } else if (isLive) {
    scoreHtml = `<div class="match-score">🔴 EN VIVO</div>`;
  } else {
    scoreHtml = `<div class="match-score" style="color:var(--gray)">vs</div>`;
  }

  // Date
  const dateStr = m.match_date ? formatMatchDate(m.match_date) : 'Fecha a confirmar';

  // Status badge
  let badge = '';
  if (isLive) badge = '<span class="match-status-badge live">EN VIVO</span>';
  else if (isFinished) badge = '<span class="match-status-badge finished">Finalizado</span>';
  else badge = '<span class="match-status-badge scheduled">Próximo</span>';

  // User prediction
  let predHtml = '';
  const pred = m.user_prediction;
  if (pred) {
    const predStr = `${pred.predicted_home_score}-${pred.predicted_away_score}`;
    if (pred.points_calculated) {
      const pts = pred.points_earned;
      const cls = `earned-${pts}`;
      const label = pts === 10 ? '🎯 Exacto' : pts === 7 ? '✅ Empate OK' : pts === 5 ? '↔️ Diferencia' : pts === 3 ? '👍 Ganador' : '❌ Perdiste';
      predHtml = `<div class="pred-result ${cls}">${label} (${pts} pts)<br><small>Tu pronóstico: ${predStr}</small></div>`;
    } else {
      predHtml = `<div class="pred-result">Tu pronóstico: <strong>${predStr}</strong></div>`;
    }
  }

  // Predict button
  let actionHtml = '';
  if (!isLocked && !isFinished && currentUser) {
    const btnClass = pred ? 'predict-btn predicted' : 'predict-btn';
    const btnLabel = pred ? '✏️ Editar' : 'Pronosticar';
    actionHtml = `<button class="${btnClass}" onclick="openPredModal(${JSON.stringify(m).replace(/"/g, '&quot;')})">${btnLabel}</button>`;
  } else if (!currentUser && !isFinished && !isLocked) {
    actionHtml = `<button class="predict-btn" onclick="navigate('register')">Registrate para pronosticar</button>`;
  }

  return `
    <div class="match-card ${isFinished ? 'finished' : ''} ${isLive ? 'live' : ''}">
      <div class="match-team">
        <div class="team-flag">${homeFlag}</div>
        <div class="team-name">${escHtml(homeName)}</div>
      </div>
      <div class="match-center">
        ${badge}
        ${scoreHtml}
        <div class="match-date">${dateStr}</div>
        ${predHtml}
        ${actionHtml}
      </div>
      <div class="match-team away">
        <div class="team-flag">${awayFlag}</div>

        <div class="team-name">${escHtml(awayName)}</div>
      </div>
    </div>
  `;
}

// ===== PREDICTION MODAL =====
function openPredModal(match) {
  currentMatchForPred = match;
  selectedPenaltyWinner = null;

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
  document.getElementById('penHomeBtn').textContent = homeName;
  document.getElementById('penAwayBtn').textContent = awayName;

  // Load existing prediction
  const pred = match.user_prediction;
  document.getElementById('predHomeScore').value = pred ? pred.predicted_home_score : 0;
  document.getElementById('predAwayScore').value = pred ? pred.predicted_away_score : 0;

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

  document.querySelectorAll('input[name="resolve"]').forEach(r => {
    r.addEventListener('change', () => {
      const isPenalties = r.value === 'pk';
      document.getElementById('penaltyWinner').style.display = isPenalties ? 'block' : 'none';
    });
  });
}

function checkKnockoutDraw() {
  const h = parseInt(document.getElementById('predHomeScore').value) || 0;
  const a = parseInt(document.getElementById('predAwayScore').value) || 0;
  const isDraw = h === a;
  document.getElementById('koResolveOptions').style.display = isDraw ? 'flex' : 'none';
  if (!isDraw) {
    document.getElementById('penaltyWinner').style.display = 'none';
  }
}

function setPenaltyWinner(side) {
  selectedPenaltyWinner = side === 'home'
    ? currentMatchForPred?.home_team?.id
    : currentMatchForPred?.away_team?.id;
  document.getElementById('penHomeBtn').classList.toggle('selected', side === 'home');
  document.getElementById('penAwayBtn').classList.toggle('selected', side === 'away');
}

function closePredModal() {
  document.getElementById('predModal').style.display = 'none';
  currentMatchForPred = null;
}

async function submitPrediction(e) {
  e.preventDefault();
  if (!currentUser) { navigate('login'); return; }

  const match = currentMatchForPred;
  const isKnockout = ['r16','qf','sf','third','final'].includes(match.phase);
  const homeScore = parseInt(document.getElementById('predHomeScore').value) || 0;
  const awayScore = parseInt(document.getElementById('predAwayScore').value) || 0;
  const isDraw = homeScore === awayScore;

  let extraTime = false;
  let penalties = false;
  let penaltyWinnerId = null;

  if (isKnockout && isDraw) {
    const resolveVal = document.querySelector('input[name="resolve"]:checked')?.value;
    if (!resolveVal) {
      showPredError('Indicá si el empate se resuelve por tiempo extra o penales');
      return;
    }
    extraTime = true;
    penalties = resolveVal === 'pk';
    if (penalties) {
      if (!selectedPenaltyWinner) {
        showPredError('Indicá qué equipo gana los penales');
        return;
      }
      penaltyWinnerId = selectedPenaltyWinner;
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
        predicted_penalty_winner_id: penaltyWinnerId
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
        <tr class="${isMe ? 'rank-highlight' : ''}">
          <td><span class="rank-pos ${cls}">${medal}</span></td>
          <td>
            <div class="rank-username">${escHtml(u.username)}${isMe ? ' <small style="color:var(--gold)">← vos</small>' : ''}</div>
            ${u.full_name ? `<div style="font-size:0.75rem;color:var(--gray)">${escHtml(u.full_name)}</div>` : ''}
          </td>
          <td>
            <div class="rank-points">${u.total_points}</div>
            <div class="rank-pts-breakdown">⚽ ${u.prediction_points} + 🛍️ ${u.purchase_points}</div>
          </td>
          <td style="font-size:0.8rem;color:var(--gray)">${u.predictions_made || 0}</td>
          <td style="font-size:0.8rem;color:var(--gold)">${u.exact_results || 0}</td>
        </tr>
      `;
    }).join('');

    container.innerHTML = `
      <table class="ranking-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Jugador</th>
            <th>Puntos</th>
            <th>Pronósticos</th>
            <th>🎯 Exactos</th>
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
  try { data = await res.json(); } catch { data = {}; }

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
    return d.toLocaleDateString('es-UY', {
      weekday: 'short', day: 'numeric', month: 'short',
      hour: '2-digit', minute: '2-digit', timeZone: 'America/Montevideo'
    });
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
  if (!email) { errEl.textContent = 'Ingresa tu email'; return; }
  btn.disabled = true;
  btn.textContent = 'Enviando...';
  errEl.textContent = '';
  try {
    const data = await apiFetch('/api/auth/forgot-password', {
      method: 'POST',
      body: JSON.stringify({ email })
    });
    errEl.style.color = 'var(--green)';
    errEl.textContent = data.message || 'Si ese email esta registrado, recibiras un link en breve.';
    btn.textContent = 'Enviado';
  } catch (e) {
    errEl.style.color = '';
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
  if (newPassword !== confirmPassword) { errEl.textContent = 'Las contrasenas no coinciden'; return; }
  if (newPassword.length < 6) { errEl.textContent = 'La contrasena debe tener al menos 6 caracteres'; return; }
  btn.disabled = true;
  btn.textContent = 'Guardando...';
  errEl.textContent = '';
  try {
    const data = await apiFetch('/api/auth/reset-password', {
      method: 'POST',
      body: JSON.stringify({ token, new_password: newPassword })
    });
    errEl.style.color = 'var(--green)';
    errEl.textContent = data.message;
    btn.textContent = 'Listo';
    setTimeout(() => navigate('login'), 2000);
  } catch (e) {
    errEl.style.color = '';
    errEl.textContent = e.message || 'Error. El link puede haber expirado.';
    btn.disabled = false;
    btn.textContent = 'Cambiar contrasena';
  }
}
