"""
=============================================================
  APLIKASI WEB ESTIMASI NILAI GADAI HP — ENONI CELL
  Backend: Python Flask
  File   : app.py
=============================================================
"""

import os
import json
import numpy as np
import joblib
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_absolute_error, r2_score

# ── Inisialisasi Flask & Database ──────────────────────────
app = Flask(__name__)
app.secret_key = 'enoni_cell_secret_123'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'mysql+pymysql://root:@localhost/db_gadai_enoni')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,      # Auto-reconnect jika koneksi MySQL terputus
    'pool_recycle': 280,        # Recycle koneksi setiap 280 detik (sebelum MySQL timeout)
    'pool_timeout': 20,
    'pool_size': 5,
    'max_overflow': 10,
}

db = SQLAlchemy(app)

# ── Model Database ─────────────────────────────────────────
class User(db.Model):
    id_user = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False) # Hashed password (Jangan 50, hash werkzeug butuh ~162 karakter)
    role = db.Column(db.Enum('superadmin', 'admin', name='user_roles'), default='admin', nullable=False)

class SpesifikasiHP(db.Model):
    __tablename__ = 'spesifikasi_hp'
    id_spek = db.Column(db.Integer, primary_key=True)
    merk = db.Column(db.String(50))
    tipe = db.Column(db.String(100))
    tahun = db.Column(db.Integer)
    ram = db.Column(db.Integer)
    storage = db.Column(db.Integer)
    kondisi = db.Column(db.Integer)
    charger = db.Column(db.Integer)
    dus = db.Column(db.Integer)
    fungsi = db.Column(db.Integer)

class HistoryEstimasi(db.Model):
    __tablename__ = 'history_estimasi'
    id_history = db.Column(db.Integer, primary_key=True)
    id_spek = db.Column(db.Integer, db.ForeignKey('spesifikasi_hp.id_spek'), nullable=False)
    tanggal = db.Column(db.DateTime, default=datetime.now)
    estimasi_harga = db.Column(db.Integer, nullable=True) # Null if model unknown
    status = db.Column(db.String(50)) # 'Sukses' or 'Gagal'
    id_user = db.Column(db.Integer, db.ForeignKey('user.id_user')) # Relasi ke User
    
    admin = db.relationship('User', backref=db.backref('history_estimasi', lazy=True))
    spesifikasi = db.relationship('SpesifikasiHP', backref=db.backref('history_estimasi', lazy=True))

class DatasetUpdate(db.Model):
    id_dataset = db.Column(db.Integer, primary_key=True)
    tanggal_upload = db.Column(db.DateTime, default=datetime.now)
    nama_file = db.Column(db.String(255))
    jumlah_baris = db.Column(db.Integer)
    akurasi_r2 = db.Column(db.Float)
    mae = db.Column(db.Float)
    status = db.Column(db.String(50))
    id_user = db.Column(db.Integer, db.ForeignKey('user.id_user')) # Foreign Key ke tabel User
    
    # Relasi agar mudah memanggil object User dari DatasetUpdate
    uploader = db.relationship('User', backref=db.backref('dataset_updates', lazy=True))

with app.app_context():
    db.create_all()
    # Buat user admin default jika tabel User masih kosong
    if not User.query.first():
        hashed_pw = generate_password_hash('admin123')
        default_admin = User(username='admin', password=hashed_pw, role='superadmin')
        db.session.add(default_admin)
        db.session.commit()
        print("[INFO] Default admin user created: admin / admin123")

@app.before_request
def require_login():
    # Rute yang boleh diakses tanpa login
    allowed_routes = ['login', 'static']
    if request.endpoint not in allowed_routes and not session.get('logged_in'):
        return redirect(url_for('login'))

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

# ── Load model & encoder saat startup ─────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR  = os.path.join(BASE_DIR, 'model')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Jadikan global agar bisa di-update saat retraining
model = None
le_merk = None
le_tipe = None
metadata = {}

def load_ml_assets():
    global model, le_merk, le_tipe, metadata
    try:
        model    = joblib.load(os.path.join(MODEL_DIR, 'model_rf_gadai.pkl'))
        le_merk  = joblib.load(os.path.join(MODEL_DIR, 'encoder_merk.pkl'))
        le_tipe  = joblib.load(os.path.join(MODEL_DIR, 'encoder_tipe.pkl'))
        with open(os.path.join(MODEL_DIR, 'metadata.json'), encoding='utf-8') as f:
            metadata = json.load(f)
        return True
    except Exception as e:
        print(f"[WARNING] Gagal memuat model: {e}")
        return False

load_ml_assets()

with open(os.path.join(MODEL_DIR, 'metadata.json'), encoding='utf-8') as f:
    pass # Already loaded in load_ml_assets

TAHUN_SKRIPSI = 2026 # Tetap ada sebagai metadata/konstanta referensi (opsional)
if model:
    print("[OK] Model dan encoder berhasil dimuat.")
print(f"   Merk tersedia : {metadata['merk_list']}")
print(f"   RAM tersedia  : {metadata['ram_list']}")


# ==============================================================
# ROUTE: Halaman Utama (Form Input)
# ==============================================================
@app.route('/')
def index():
    """Tampilkan halaman form input estimasi gadai."""
    return render_template(
        'index.html',
        merk_list    = metadata['merk_list'],
        tipe_per_merk= metadata['tipe_per_merk'],
        ram_list     = metadata['ram_list'],
        storage_list = metadata['storage_list'],
        tahun_min    = metadata['tahun_min'],
        tahun_max    = metadata['tahun_max'],
    )


# ==============================================================
# ROUTE: API Estimasi (AJAX POST)
# ==============================================================
@app.route('/estimasi', methods=['POST'])
def estimasi():
    """Terima data HP dari form, kembalikan estimasi nilai gadai."""
    try:
        data = request.get_json()
        current_user = User.query.filter_by(username=session.get('username')).first() if session.get('username') else None

        # ── Validasi input ─────────────────────────────────
        merk    = data.get('merk', '').strip()
        tipe    = data.get('tipe', '').strip().lower()
        tahun   = int(data.get('tahun', 0))
        ram     = int(data.get('ram', 0))
        storage = int(data.get('storage', 0))
        kondisi = int(data.get('kondisi', 0))
        charger = int(data.get('charger', 0))
        dus     = int(data.get('dus', 0))
        fungsi  = int(data.get('fungsi', 1))

        # Jika merk atau tipe tidak valid secara model, biarkan prediksi kosong tapi jadikan status 'Gagal'
        error_msg = None
        if merk not in le_merk.classes_:
            error_msg = f'Merk "{merk}" tidak dikenali model.'
        elif tipe not in le_tipe.classes_:
            error_msg = f'Tipe "{tipe}" tidak ada dalam data training.'

        if error_msg:
            # Simpan spesifikasi HP gagal
            spek = SpesifikasiHP(
                merk=merk, tipe=tipe, tahun=tahun, ram=ram, storage=storage,
                kondisi=kondisi, charger=charger, dus=dus, fungsi=fungsi
            )
            db.session.add(spek)
            db.session.flush()

            # Simpan riwayat gagal tanpa estimasi harga
            history = HistoryEstimasi(
                id_spek=spek.id_spek,
                estimasi_harga=None, status='Gagal: Tipe/Merk tidak dikenal',
                id_user=current_user.id_user if current_user else None
            )
            db.session.add(history)
            db.session.commit()
            return jsonify({'status': 'error', 'pesan': error_msg + ' Data telah tersimpan untuk review Admin.'})

        # ── Preprocessing (sama persis dengan saat training) ──
        merk_enc = int(le_merk.transform([merk])[0])
        tipe_enc = int(le_tipe.transform([tipe])[0])
        # Menghitung umur HP secara dinamis berdasarkan tahun saat ini
        tahun_sekarang = datetime.now().year
        usia_hp  = tahun_sekarang - tahun

        fitur = np.array([[
            merk_enc,   # merk_enc
            tipe_enc,   # tipe_enc
            tahun,      # tahun
            usia_hp,    # usia_hp
            ram,        # ram
            storage,    # storage
            kondisi,    # kondisi
            charger,    # charger_enc
            dus,        # dus_enc
            fungsi,     # fungsi_enc
        ]])

        # ── Prediksi ──────────────────────────────────────
        hasil = model.predict(fitur)[0]
        hasil = max(0, int(round(hasil, -3)))   # bulatkan ke ribuan

        # ── Kategori nilai ────────────────────────────────
        if hasil < 300_000:
            kategori = 'Rendah'
            warna    = 'warning'
        elif hasil < 700_000:
            kategori = 'Menengah'
            warna    = 'info'
        else:
            kategori = 'Tinggi'
            warna    = 'success'

        # ── Simpan spesifikasi HP sukses ──────────────────
        spek = SpesifikasiHP(
            merk=merk, tipe=tipe, tahun=tahun, ram=ram, storage=storage,
            kondisi=kondisi, charger=charger, dus=dus, fungsi=fungsi
        )
        db.session.add(spek)
        db.session.flush()

        # ── Simpan ke Database ────────────────────────────
        history = HistoryEstimasi(
            id_spek=spek.id_spek,
            estimasi_harga=hasil, status='Sukses',
            id_user=current_user.id_user if current_user else None
        )
        db.session.add(history)
        db.session.commit()

        return jsonify({
            'status'   : 'ok',
            'estimasi' : hasil,
            'estimasi_fmt': f'Rp {hasil:,}'.replace(',', '.'),
            'kategori' : kategori,
            'warna'    : warna,
            'detail'   : {
                'merk'    : merk,
                'tipe'    : tipe.title(),
                'tahun'   : tahun,
                'usia'    : usia_hp,
                'ram'     : ram,
                'storage' : storage,
                'kondisi' : 'Mulus' if kondisi == 5 else 'Baret ringan',
                'charger' : 'Ada' if charger else 'Tidak',
                'dus'     : 'Ada' if dus else 'Tidak',
                'fungsi'  : 'Normal' if fungsi else 'Tidak normal',
            }
        })

    except Exception as e:
        return jsonify({'status': 'error', 'pesan': str(e)})


# ==============================================================
# ROUTE: API daftar tipe berdasarkan merk (untuk dropdown dinamis)
# ==============================================================
@app.route('/tipe/<merk>')
def get_tipe(merk):
    """Kembalikan daftar tipe HP berdasarkan merk yang dipilih."""
    tipe_list = metadata['tipe_per_merk'].get(merk, [])
    return jsonify({'tipe_list': tipe_list})

# ==============================================================
# ROUTE: Login dan Dashboard
# ==============================================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Cari user dari Database
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['logged_in'] = True
            session['username'] = user.username
            session['role'] = user.role
            flash('Login berhasil!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Username atau password salah.', 'danger')
            return render_template('login.html', error="Username atau Password salah")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('Anda telah logout.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    histories = HistoryEstimasi.query.order_by(HistoryEstimasi.tanggal.desc()).limit(100).all()
    
    # Data grafik: tren prediksi yang sukses
    sukses_data = HistoryEstimasi.query.filter_by(status='Sukses').order_by(HistoryEstimasi.tanggal.asc()).all()
    
    labels = [h.tanggal.strftime("%Y-%m-%d %H:%M") for h in sukses_data]
    prices = [h.estimasi_harga for h in sukses_data]
    model_names = [f"{h.spesifikasi.merk} {h.spesifikasi.tipe}" for h in sukses_data]
    
    return render_template(
        'dashboard.html', 
        histories=histories,
        graph_labels=labels,
        graph_prices=prices,
        graph_models=model_names
    )

# ==============================================================
# ROUTE: Kelola Dataset & Retraining
# ==============================================================
@app.route('/dataset')
def dataset():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    updates = DatasetUpdate.query.order_by(DatasetUpdate.tanggal_upload.desc()).all()
    return render_template('dataset.html', updates=updates)

@app.route('/download_template')
def download_template():
    import io
    import pandas as pd
    from flask import send_file
    from openpyxl.styles import Font, PatternFill, Alignment
    
    data = {
        'merk': ['Samsung', 'Xiaomi', 'Apple', 'Oppo', 'Vivo'],
        'tipe': ['Galaxy A50', 'Redmi Note 10', 'iPhone 11', 'Reno 5', 'V20'],
        'tahun': [2019, 2021, 2019, 2020, 2020],
        'ram': [4, 4, 4, 8, 8],
        'storage': [64, 128, 64, 128, 128],
        'kondisi': [5, 4, 5, 4, 5],
        'charger': [1, 1, 1, 1, 0],
        'dus': [1, 0, 1, 1, 1],
        'fungsi': [1, 1, 1, 1, 1],
        'harga': [1500000, 1800000, 4500000, 2200000, 2100000]
    }
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Template_Gadai')
        worksheet = writer.sheets['Template_Gadai']
        
        # Styling Header
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1F2937", end_color="1F2937", fill_type="solid")
        alignment = Alignment(horizontal="center", vertical="center")
        
        for cell in worksheet["1:1"]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = alignment
            
        # Auto-adjust column width
        for column in worksheet.columns:
            max_length = 0
            column_name = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
                except:
                    pass
            worksheet.column_dimensions[column_name].width = max_length + 2

    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='Template_Dataset_EnoniCell.xlsx'
    )

@app.route('/upload_dataset', methods=['POST'])
def upload_dataset():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    if 'file_dataset' not in request.files:
        flash('Tidak ada file yang diunggah.', 'danger')
        return redirect(url_for('dataset'))
        
    file = request.files['file_dataset']
    if file.filename == '':
        flash('File belum dipilih.', 'danger')
        return redirect(url_for('dataset'))
        
    if not (file.filename.endswith('.csv') or file.filename.endswith('.xlsx')):
        flash('Format file harus .csv atau .xlsx!', 'danger')
        return redirect(url_for('dataset'))
        
    try:
        # 1. Simpan file
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_DIR, filename)
        file.save(filepath)
        
        # 2. Baca dengan pandas
        if filename.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
            
        jumlah_baris = len(df)
        
        # Validasi kolom yang dibutuhkan
        required_cols = ['merk', 'tipe', 'tahun', 'ram', 'storage', 'kondisi', 'charger', 'dus', 'fungsi', 'harga']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Kolom dataset tidak lengkap. Kurang: {', '.join(missing_cols)}")
            
        # 3. Retraining Model
        # Karena ini data baru, kita butuh fit ulang LabelEncoder
        # Untuk skripsi, kita asumsikan dataset CSV ini adalah dataset LENGKAP (gabungan lama + baru)
        # Jika bukan gabungan, sebaiknya dataset digabung dulu. Di sini kita asumsikan ini full dataset.
        
        # Fit Encoder
        new_le_merk = LabelEncoder()
        new_le_tipe = LabelEncoder()
        
        df['merk_enc'] = new_le_merk.fit_transform(df['merk'].astype(str))
        df['tipe_enc'] = new_le_tipe.fit_transform(df['tipe'].astype(str))
        df['usia_hp'] = datetime.now().year - df['tahun']
        
        X = df[['merk_enc', 'tipe_enc', 'tahun', 'usia_hp', 'ram', 'storage', 'kondisi', 'charger', 'dus', 'fungsi']]
        y = df['harga']
        
        # Fit Random Forest
        new_model = RandomForestRegressor(n_estimators=100, random_state=42)
        new_model.fit(X, y)
        
        # Evaluasi pada data training (untuk simplifikasi, idealnya train_test_split)
        y_pred = new_model.predict(X)
        r2 = r2_score(y, y_pred)
        mae = mean_absolute_error(y, y_pred)
        
        # 4. Simpan model & encoder baru
        joblib.dump(new_model, os.path.join(MODEL_DIR, 'model_rf_gadai.pkl'))
        joblib.dump(new_le_merk, os.path.join(MODEL_DIR, 'encoder_merk.pkl'))
        joblib.dump(new_le_tipe, os.path.join(MODEL_DIR, 'encoder_tipe.pkl'))
        
        # 5. Update Metadata
        merk_list = sorted(list(df['merk'].unique()))
        tipe_per_merk = {}
        for m in merk_list:
            tipe_per_merk[m] = sorted(list(df[df['merk'] == m]['tipe'].unique()))
            
        new_metadata = {
            "merk_list": merk_list,
            "tipe_per_merk": tipe_per_merk,
            "ram_list": sorted([int(x) for x in df['ram'].unique()]),
            "storage_list": sorted([int(x) for x in df['storage'].unique()]),
            "tahun_min": int(df['tahun'].min()),
            "tahun_max": int(df['tahun'].max())
        }
        with open(os.path.join(MODEL_DIR, 'metadata.json'), 'w', encoding='utf-8') as f:
            json.dump(new_metadata, f, indent=4)
            
        # 6. Reload ke global variable
        load_ml_assets()
        
        # 7. Simpan riwayat update ke DB
        current_user = User.query.filter_by(username=session['username']).first()
        
        update_record = DatasetUpdate(
            nama_file=filename,
            jumlah_baris=jumlah_baris,
            akurasi_r2=r2,
            mae=mae,
            status='Sukses',
            id_user=current_user.id_user if current_user else None
        )
        db.session.add(update_record)
        db.session.commit()
        
        flash(f'Dataset berhasil diupload & Model dilatih ulang! Akurasi (R²): {r2:.4f}, MAE: Rp {mae:,.0f}', 'success')
        
    except Exception as e:
        flash(f'Gagal memproses dataset: {str(e)}', 'danger')
        
    return redirect(url_for('dataset'))

# ==============================================================
# ROUTE: Kelola Admin (Superadmin Only)
# ==============================================================
@app.route('/users')
def users():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if session.get('role') != 'superadmin':
        flash('Akses ditolak! Anda bukan Superadmin.', 'danger')
        return redirect(url_for('dashboard'))
        
    all_users = User.query.all()
    return render_template('users.html', users=all_users)

@app.route('/add_user', methods=['POST'])
def add_user():
    if not session.get('logged_in') or session.get('role') != 'superadmin':
        return redirect(url_for('login'))
        
    username = request.form.get('username')
    password = request.form.get('password')
    role = request.form.get('role')
    
    if User.query.filter_by(username=username).first():
        flash('Username sudah digunakan!', 'danger')
    else:
        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, password=hashed_pw, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash('Akun admin berhasil ditambahkan!', 'success')
        
    return redirect(url_for('users'))

@app.route('/delete_user/<int:id_user>')
def delete_user(id_user):
    if not session.get('logged_in') or session.get('role') != 'superadmin':
        return redirect(url_for('login'))
        
    user = User.query.get_or_404(id_user)
    if user.username == session['username']:
        flash('Anda tidak bisa menghapus akun Anda sendiri!', 'danger')
    else:
        # Jika user yang dihapus memiliki riwayat dataset update, set user_id ke Null (sudah dihandle db default behavior atau biarkan)
        db.session.delete(user)
        db.session.commit()
        flash('Akun admin berhasil dihapus!', 'success')
        
    return redirect(url_for('users'))


# ==============================================================
# MAIN
# ==============================================================
if __name__ == '__main__':
    print("\n[START] Aplikasi Estimasi Gadai HP — Enoni Cell")
    print("   Akses di: http://127.0.0.1:5005\n")
    app.run(debug=True, host='0.0.0.0', port=5005)
