/* ============================================================
   MAIN.JS — Estimasi Gadai HP Enoni Cell
   ============================================================ */

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

// ── Helper: tampilkan state ───────────────────────────────
function showState(state) {
  [stateEmpty, stateLoading, stateError, stateHasil].forEach(el => {
    el.style.display = 'none';
  });
  state.style.display = (state === stateHasil) ? 'block' : 'flex';
}


// ── Toggle switch — update label Ya/Tidak ────────────────
['charger', 'dus', 'fungsi'].forEach(id => {
  const input = document.getElementById(id);
  const label = document.getElementById('val-' + id);
  if (!input || !label) return;

  // Set nilai awal
  label.textContent = input.checked ? 'Ya' : 'Tidak';
  label.style.color = input.checked ? '#2E7D32' : '#9AA0A6';

  input.addEventListener('change', function () {
    label.textContent = this.checked ? 'Ya' : 'Tidak';
    label.style.color = this.checked ? '#2E7D32' : '#9AA0A6';
  });
});

// ── Format angka ke Rupiah ────────────────────────────────
function formatRp(angka) {
  return 'Rp ' + angka.toLocaleString('id-ID');
}

// ── Submit form ───────────────────────────────────────────
formEstimasi.addEventListener('submit', async function (e) {
  e.preventDefault(); // <-- Ini gunanya untuk mencegah browser me-reload halaman

  // Kumpulkan data dari form
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

  // Validasi sederhana
  if (!payload.merk || !payload.tipe || !payload.tahun ||
      !payload.ram  || !payload.storage) {
    alert('Lengkapi semua field yang wajib diisi!');
    return;
  }

  // Tampilkan loading
  showState(stateLoading);
  btnEstimasi.classList.add('loading');
  btnEstimasi.disabled = true;

  try {
    const res = await fetch('/estimasi', {
      method : 'POST',
      headers: { 'Content-Type': 'application/json' },
      body   : JSON.stringify(payload),
    }); // Mengirim spesifikasi HP yang diisi user

    const data = await res.json(); // Menerima hasil prediksi dari Flask

    if (data.status === 'error') {
      errorMsg.textContent = data.pesan || 'Terjadi kesalahan pada server.';
      showState(stateError);
      return;
    }

    // ── Tampilkan hasil ───────────────────────────────
    nilaiAngka.textContent = data.estimasi_fmt; // Nilai gadai di layar langsung berubah!

    // Warna badge sesuai kategori
    nilaiBadge.textContent = data.kategori;
    nilaiBadge.style.background = {
      'success': 'rgba(46,125,50,.25)',
      'warning': 'rgba(186,117,23,.25)',
      'info'   : 'rgba(21,101,192,.25)',
    }[data.warna] || 'rgba(255,255,255,.2)';

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

    showState(stateHasil);

  } catch (err) {
    errorMsg.textContent = 'Gagal terhubung ke server. Pastikan aplikasi berjalan.';
    showState(stateError);
    console.error(err);
  } finally {
    btnEstimasi.classList.remove('loading');
    btnEstimasi.disabled = false;
  }
});

// ── Reset form ────────────────────────────────────────────
function resetForm() {
  formEstimasi.reset();
  selTipe.value = '';

  // Reset toggle labels
  ['charger', 'dus'].forEach(id => {
    const lbl = document.getElementById('val-' + id);
    if (lbl) { lbl.textContent = 'Tidak'; lbl.style.color = '#9AA0A6'; }
  });
  const lblFungsi = document.getElementById('val-fungsi');
  if (lblFungsi) { lblFungsi.textContent = 'Ya'; lblFungsi.style.color = '#2E7D32'; }

  showState(stateEmpty);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
