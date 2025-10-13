(function() {
  const trumpSel = document.querySelector('select[name="trump"]');
  const beloteA = document.querySelector('input[name="belote_a"]');
  const beloteB = document.querySelector('input[name="belote_b"]');
  const contractSel = document.getElementById('contract');
  const generalCb = document.getElementById('general');
  const scoreAInput = document.querySelector('input[name="score_team_a"]');
  const scoreBInput = document.querySelector('input[name="score_team_b"]');
  const takerSel = document.querySelector('select[name="taker_user_id"]');
  let updatingScore = false;

  function updateBeloteMax() {
    const isToutAtout = (trumpSel?.value || '').toLowerCase() === 'tout atout';
    if (beloteA) {
      if (isToutAtout) {
        beloteA.removeAttribute('max');
      } else {
        beloteA.setAttribute('max', '1');
        if (parseInt(beloteA.value || '0', 10) > 1) beloteA.value = '1';
      }
    }
    if (beloteB) {
      if (isToutAtout) {
        beloteB.removeAttribute('max');
      } else {
        beloteB.setAttribute('max', '1');
        if (parseInt(beloteB.value || '0', 10) > 1) beloteB.value = '1';
      }
    }
  }

  function syncSpecialFromContract() {
    const v = contractSel?.value || '';
    if (generalCb) generalCb.checked = (v === 'Générale');
    if (v === 'Générale') {
      setScoresForTaker162();
    }
  }

  function enforceBeloteSumPerTrump() {
    const t = (trumpSel?.value || '').toLowerCase();
    let a = parseInt(beloteA?.value || '0', 10) || 0;
    let b = parseInt(beloteB?.value || '0', 10) || 0;
    if (t === 'sans atout') {
      if (beloteA) beloteA.value = '0';
      if (beloteB) beloteB.value = '0';
      return;
    }
    if (t === 'tout atout') {
      if (a + b > 4) {
        const excess = a + b - 4;
        const reduceB = Math.min(excess, b);
        b -= reduceB;
        const reduceA = excess - reduceB;
        a -= reduceA;
        if (beloteA) beloteA.value = String(Math.max(0, a));
        if (beloteB) beloteB.value = String(Math.max(0, b));
      }
      return;
    }
    if (a + b > 1) {
      if (beloteB) beloteB.value = '0';
    }
  }

  function clamp0to162(n) {
    n = isNaN(n) ? 0 : n;
    if (n < 0) return 0;
    if (n > 162) return 162;
    return n;
  }

  function complementScores(changed) {
    if (updatingScore) return;
    updatingScore = true;
    try {
      if (changed === 'A' && scoreAInput && scoreBInput) {
        const a = scoreAInput.value === '' ? null : clamp0to162(parseInt(scoreAInput.value, 10));
        if (a === null) {
          scoreBInput.value = '';
        } else {
          scoreAInput.value = String(a);
          scoreBInput.value = String(162 - a);
        }
      } else if (changed === 'B' && scoreAInput && scoreBInput) {
        const b = scoreBInput.value === '' ? null : clamp0to162(parseInt(scoreBInput.value, 10));
        if (b === null) {
          scoreAInput.value = '';
        } else {
          scoreBInput.value = String(b);
          scoreAInput.value = String(162 - b);
        }
      }
    } finally {
      updatingScore = false;
    }
  }

  function getTakerTeam() {
    if (!takerSel) return null;
    const opt = takerSel.selectedOptions && takerSel.selectedOptions[0];
    if (!opt) return null;
    const dataTeam = opt.getAttribute('data-team');
    if (dataTeam === 'A' || dataTeam === 'B') return dataTeam;
    const txt = opt.textContent || '';
    const m = txt.match(/\((A|B)\)/);
    return m ? m[1] : null;
  }

  function setScoresForTaker162() {
    const team = getTakerTeam();
    if (!team) return;
    updatingScore = true;
    try {
      if (team === 'A') {
        if (scoreAInput) scoreAInput.value = '162';
        if (scoreBInput) scoreBInput.value = '0';
      } else if (team === 'B') {
        if (scoreBInput) scoreBInput.value = '162';
        if (scoreAInput) scoreAInput.value = '0';
      }
    } finally {
      updatingScore = false;
    }
  }

  trumpSel && trumpSel.addEventListener('change', function() {
    updateBeloteMax();
    enforceBeloteSumPerTrump();
  });
  contractSel && contractSel.addEventListener('change', syncSpecialFromContract);
  takerSel && takerSel.addEventListener('change', function() {
    if (generalCb && generalCb.checked) {
      setScoresForTaker162();
    }
  });
  beloteA && beloteA.addEventListener('input', function() { enforceBeloteSumPerTrump(); });
  beloteB && beloteB.addEventListener('input', function() { enforceBeloteSumPerTrump(); });
  scoreAInput && scoreAInput.addEventListener('input', function() { complementScores('A'); });
  scoreBInput && scoreBInput.addEventListener('input', function() { complementScores('B'); });
  generalCb && generalCb.addEventListener('change', function() {
    if (generalCb.checked) setScoresForTaker162();
  });
  updateBeloteMax();
  syncSpecialFromContract();
  enforceBeloteSumPerTrump();
})();
