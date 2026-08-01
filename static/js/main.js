// ── Mobile Navbar Toggle ─────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  const navToggle = document.getElementById('navToggle');
  const navLinks = document.getElementById('navLinks');
  
  if (navToggle && navLinks) {
    let lastToggleTime = 0;

    function toggleMenu(e) {
      if (e) {
        e.preventDefault();
        e.stopPropagation();
      }
      
      const now = Date.now();
      if (now - lastToggleTime < 300) return;
      lastToggleTime = now;

      const isOpen = navLinks.classList.toggle('show');
      navToggle.classList.toggle('open', isOpen);
      navToggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
      
      const iconH = navToggle.querySelector('.icon-hamburger');
      const iconC = navToggle.querySelector('.icon-close');
      if (iconH && iconC) {
        iconH.style.display = isOpen ? 'none' : 'inline';
        iconC.style.display = isOpen ? 'inline' : 'none';
      } else {
        navToggle.textContent = isOpen ? '✕' : '☰';
      }

      // Cegah tap-through / ghost click pada HP saat menu baru terbuka
      if (isOpen) {
        navLinks.style.pointerEvents = 'none';
        setTimeout(() => {
          navLinks.style.pointerEvents = '';
        }, 300);
      }
    }

    navToggle.addEventListener('click', toggleMenu);

    document.addEventListener('click', function (e) {
      if (navLinks.classList.contains('show')) {
        if (!navLinks.contains(e.target) && !navToggle.contains(e.target) && !e.target.closest('#navToggle')) {
          navLinks.classList.remove('show');
          navToggle.classList.remove('open');
          navToggle.setAttribute('aria-expanded', 'false');
          const iconH = navToggle.querySelector('.icon-hamburger');
          const iconC = navToggle.querySelector('.icon-close');
          if (iconH && iconC) {
            iconH.style.display = 'inline';
            iconC.style.display = 'none';
          } else {
            navToggle.textContent = '☰';
          }
        }
      }
    });
  }
});

'use strict';

// ── Referensi elemen DOM ──────────────────────────────────
const formEstimasi  = document.getElementById('formEstimasi');
const selMerk       = document.getElementById('merk');
const selTipe       = document.getElementById('tipe');
const btnEstimasi   = document.getElementById('btnEstimasi');

const stateEmpty    = document.getElementById('stateEmpty');
const stateLoading  = document.getElementById('stateLoading');
const stateError    = document.getElementById('stateError');
const stateHasil    = document.getElementById('stateHasil');
const errorMsg      = document.getElementById('errorMsg');
const nilaiAngka    = document.getElementById('nilaiAngka');
const nilaiBadge    = document.getElementById('nilaiBadge');
const detailGrid    = document.getElementById('detailGrid');
const btnWa         = document.getElementById('btnWa');

// ── Helper: tampilkan state ───────────────────────────────
function showState(state) {
  [stateEmpty, stateLoading, stateError, stateHasil].forEach(el => {
    if (el) el.style.display = 'none';
  });
  if (state) {
    state.style.display = (state === stateHasil) ? 'block' : 'flex';
  }
}

// ── Toggle switch — update label Ya/Tidak ────────────────
['charger', 'dus', 'fungsi'].forEach(id => {
  const input = document.getElementById(id);
  const label = document.getElementById('val-' + id);
  if (!input || !label) return;

  // Set nilai awal
  label.textContent = input.checked ? 'Ya' : 'Tidak';

  input.addEventListener('change', function () {
    label.textContent = this.checked ? 'Ya' : 'Tidak';
  });
});

// ── Format angka ke Rupiah ────────────────────────────────
function formatRp(angka) {
  return 'Rp ' + angka.toLocaleString('id-ID');
}

// ── Submit form ───────────────────────────────────────────
if (formEstimasi) {
  formEstimasi.addEventListener('submit', async function (e) {
    e.preventDefault();

    const kondisiEl = document.querySelector('input[name="kondisi"]:checked');
    if (!kondisiEl) {
      alert('Pilih kondisi fisik HP terlebih dahulu!');
      return;
    }

    const payload = {
      merk   : selMerk.value,
      tipe   : selTipe.value,
      tahun  : parseInt(document.getElementById('tahun').value),
      ram    : parseInt(document.getElementById('ram').value),
      storage: parseInt(document.getElementById('storage').value),
      kondisi: parseInt(kondisiEl.value),
      charger: document.getElementById('charger').checked ? 1 : 0,
      dus    : document.getElementById('dus').checked ? 1 : 0,
      fungsi : document.getElementById('fungsi').checked ? 1 : 0,
    };

    if (!payload.merk || !payload.tipe || !payload.tahun ||
        !payload.ram  || !payload.storage) {
      alert('Lengkapi semua field yang wajib diisi!');
      return;
    }

    showState(stateLoading);
    if (btnEstimasi) {
      btnEstimasi.classList.add('loading');
      btnEstimasi.disabled = true;
    }

    try {
      const res = await fetch('/estimasi', {
        method : 'POST',
        headers: { 'Content-Type': 'application/json' },
        body   : JSON.stringify(payload),
      });

      const data = await res.json();

      if (data.status === 'error') {
        errorMsg.textContent = data.pesan || 'Terjadi kesalahan pada server.';
        showState(stateError);
        return;
      }

      // Tampilkan hasil
      nilaiAngka.textContent = data.estimasi_fmt;
      nilaiBadge.textContent = data.kategori;

      // Detail grid
      const detail = data.detail;
      const items  = [
        ['Merk',      detail.merk],
        ['Tipe',      detail.tipe],
        ['Tahun',     detail.tahun],
        ['Usia HP',   detail.usia + ' tahun'],
        ['RAM',       detail.ram + ' GB'],
        ['Storage',   detail.storage + ' GB'],
        ['Kondisi',   detail.kondisi],
        ['Charger',   detail.charger],
        ['Dus/Box',   detail.dus],
        ['Fungsi',    detail.fungsi],
      ];

      detailGrid.innerHTML = items.map(([k, v]) => `
        <div class="detail-item">
          <div class="detail-key">${k}</div>
          <div class="detail-val">${v}</div>
        </div>
      `).join('');

      // Setup WA Link
      if (btnWa) {
        const waText = `Halo Admin Enoni Cell, saya ingin konsultasi gadai HP berikut:\n\n📱 *GTI / Device*: ${detail.merk} ${detail.tipe} (${detail.tahun})\n💾 *Spek*: ${detail.ram}GB / ${detail.storage}GB\n✨ *Kondisi*: ${detail.kondisi}\n📦 *Kelengkapan*: Charger (${detail.charger}), Dus (${detail.dus})\n💰 *Estimasi System*: ${data.estimasi_fmt}\n\nMohon info proses selanjutnya ya kak.`;
        btnWa.href = `https://wa.me/6281234567890?text=${encodeURIComponent(waText)}`;
      }

      showState(stateHasil);

    } catch (err) {
      errorMsg.textContent = 'Gagal terhubung ke server. Pastikan aplikasi berjalan.';
      showState(stateError);
      console.error(err);
    } finally {
      if (btnEstimasi) {
        btnEstimasi.classList.remove('loading');
        btnEstimasi.disabled = false;
      }
    }
  });
}

// ── Print Struk / Estimasi ────────────────────────────────
function cetakStruk() {
  window.print();
}

// ── Reset form ────────────────────────────────────────────
function resetForm() {
  if (formEstimasi) formEstimasi.reset();
  if (selTipe) selTipe.value = '';

  ['charger', 'dus'].forEach(id => {
    const lbl = document.getElementById('val-' + id);
    if (lbl) lbl.textContent = 'Tidak';
  });
  const lblFungsi = document.getElementById('val-fungsi');
  if (lblFungsi) lblFungsi.textContent = 'Ya';

  showState(stateEmpty);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
