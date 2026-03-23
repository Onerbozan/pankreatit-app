import streamlit as st
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials

# --- AYARLAR VE VERİTABANI ---
st.set_page_config(page_title="Akut Pankreatit Çalışması", layout="wide")
SHEET_URL = "https://docs.google.com/spreadsheets/d/1fTA-MdaaV5CU812aPn1bZZc1KIMWey-P84jAqIbBYOA/edit?gid=0#gid=0"

COLS = [
    "TC_No", "Ad_Soyad", "Yas", "Cinsiyet", "Etiyoloji", "Semptom_Suresi", "GKS", 
    "Ates", "Nabiz", "Solunum", "Sistolik", "Diyastolik", "SpO2", "Plevral_Efuzyon", 
    "BUN", "WBC", "Amilaz", "Lipaz", "Glukoz", "Kreatinin", "Na", "K", "AST", "ALT", 
    "Bilirubin", "Albumin", "Htc", "Hgb", "Plt", "Laktat", "pH", "PaCO2", "PaO2", "HCO3", 
    "Atlanta", "Yatis_Karari", "Yatis_Yeri", "YBU_Sure", "Toplam_Sure", "Lokal_Komp", 
    "Mudahale", "Mortalite", "SIRS_Skoru", "BISAP_Skoru", "CTSI_Skoru", "MCTSI_Skoru"
]

@st.cache_resource
def get_gspread_client():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def veri_yukle():
    client = get_gspread_client()
    sheet = client.open_by_url(SHEET_URL).sheet1
    data = sheet.get_all_values()
    if not data:
        sheet.update(values=[COLS], range_name='A1')
        return pd.DataFrame(columns=COLS)
    headers = data.pop(0)
    df = pd.DataFrame(data, columns=headers)
    if 'TC_No' in df.columns:
        df['TC_No'] = df['TC_No'].astype(str)
    return df

def veri_kaydet(df):
    client = get_gspread_client()
    sheet = client.open_by_url(SHEET_URL).sheet1
    sheet.clear()
    sheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name='A1')

def get_val(df, idx, col, default=0.0):
    val = df.at[idx, col]
    if pd.isna(val) or str(val).strip() == "":
        return default
    try:
        # Virgüllü sayı girilirse noktaya çevir, hata varsa sıfır kabul et
        temiz_deger = str(val).replace(",", ".").strip()
        return float(temiz_deger)
    except ValueError:
        return default

# --- OTOMATİK SKOR HESAPLAMA FONKSİYONLARI ---
def sirs_hesapla(ates, nabiz, solunum, wbc):
    skor = 0
    try:
        f_ates = float(ates) if ates not in ["", None] else 36.5
        f_nabiz = float(nabiz) if nabiz not in ["", None] else 80
        f_solunum = float(solunum) if solunum not in ["", None] else 16
        f_wbc = float(wbc) if wbc not in ["", None] else 0.0

        if f_ates > 38 or (f_ates > 0 and f_ates < 36): skor += 1
        if f_nabiz > 90: skor += 1
        if f_solunum > 20: skor += 1
        if f_wbc != 0 and (f_wbc > 12000 or f_wbc < 4000): skor += 1
    except:
        pass
    return skor

def bisap_hesapla(bun, gks, sirs, yas, plevral):
    skor = 0
    try:
        f_bun = float(bun) if bun not in ["", None] else 0.0
        f_gks = float(gks) if gks not in ["", None] else 15
        f_sirs = float(sirs) if sirs not in ["", None] else 0
        f_yas = float(yas) if yas not in ["", None] else 0

        if f_bun >= 25: skor += 1
        if f_gks < 15: skor += 1
        if f_sirs >= 2: skor += 1
        if f_yas >= 60: skor += 1
        if plevral == "Var": skor += 1
    except:
        pass
    return skor

# --- GİRİŞ PANELİ (LOGIN) ---
if "kullanici_rolu" not in st.session_state:
    st.session_state.kullanici_rolu = None

if st.session_state.kullanici_rolu is None:
    st.title("🏥 Akut Pankreatit Çalışması Portalı")
    st.write("Lütfen giriş yapınız.")
    
    kullanici_adi = st.text_input("Kullanıcı Adı")
    sifre = st.text_input("Şifre", type="password")
    
    if st.button("Giriş Yap"):
        if kullanici_adi == "Acil" and sifre == "0322":
            st.session_state.kullanici_rolu = "Acil Hekimi"
            st.rerun()
        elif kullanici_adi == "Radyolog" and sifre == "1230":
            st.session_state.kullanici_rolu = "Radyolog"
            st.rerun()
        else:
            st.error("Hatalı kullanıcı adı veya şifre!")

# --- ACİL HEKİMİ EKRANI ---
elif st.session_state.kullanici_rolu == "Acil Hekimi":
    st.title("👨‍⚕️ Acil Hekimi Paneli")
    if st.button("Çıkış Yap"):
        st.session_state.kullanici_rolu = None
        st.rerun()
        
    sekme1, sekme2, sekme3 = st.tabs(["📋 Yeni Hasta Kaydı", "🔬 Laboratuvar Girişi", "🏥 Yatış ve Sonlanım"])
    
    df = veri_yukle()
    
    with sekme1:
        st.subheader("Yeni Hasta Ekle")
        tc = st.text_input("TC Kimlik No (11 Hane)", max_chars=11)
        ad = st.text_input("Hasta Adı Soyadı")
        
        c1, c2, c3, c4 = st.columns(4)
        yas = c1.number_input("Yaş", min_value=18, max_value=120, step=1)
        cinsiyet = c2.selectbox("Cinsiyet", ["Erkek", "Kadın"])
        semptom = c3.number_input("Semptom Süresi (saat)", min_value=0, value=0)
        etiyoloji = c4.selectbox("Etiyoloji", ["Biliar", "Alkol ilişkili", "Hipertrigliseridemi", "Post-ERCP", "İlaç ilişkili", "İdiopatik", "Diğer"])
        
        st.markdown("**Vital Bulgular ve Klinik**")
        v1, v2, v3, v4 = st.columns(4)
        ates = v1.number_input("Vücut Isısı (°C)", value=36.5, step=0.1)
        nabiz = v2.number_input("Kalp Hızı (/dk)", value=80)
        solunum = v3.number_input("Solunum Sayısı (/dk)", value=16)
        spo2 = v4.number_input("SpO2 (%)", value=98)
        
        v5, v6, v7, v8 = st.columns(4)
        sistolik = v5.number_input("Sistolik KB", value=120)
        diyastolik = v6.number_input("Diyastolik KB", value=80)
        gks = v7.selectbox("Glasgow Koma Skoru", range(3, 16), index=12)
        plevral = v8.radio("Plevral Efüzyon", ["Yok", "Var"])
        
        if st.button("Hastayı Kaydet"):
            if len(tc) == 11 and ad:
                yeni_veri = {col: "" for col in COLS}
                yeni_veri.update({
                    "TC_No": str(tc), "Ad_Soyad": ad, "Yas": yas, "Cinsiyet": cinsiyet, "Etiyoloji": etiyoloji,
                    "Semptom_Suresi": semptom, "GKS": gks, "Ates": ates, "Nabiz": nabiz, "Solunum": solunum,
                    "Sistolik": sistolik, "Diyastolik": diyastolik, "SpO2": spo2, "Plevral_Efuzyon": plevral
                })
                df = pd.concat([df, pd.DataFrame([yeni_veri])], ignore_index=True)
                veri_kaydet(df)
                st.success("Hasta başarıyla Google Sheets'e kaydedildi!")
            else:
                st.error("Lütfen TC (11 hane) ve Ad Soyad alanlarını doldurun.")

    with sekme2:
        st.subheader("Laboratuvar Sonuçlarını İşle")
        hasta_secim = st.selectbox("Lab İçin Hasta Seçin", df["TC_No"] + " - " + df["Ad_Soyad"] if not df.empty else ["Hasta Yok"], key="lab_secim")
        
        if not df.empty and hasta_secim != "Hasta Yok":
            secilen_tc = hasta_secim.split(" - ")[0]
            idx = df[df["TC_No"] == secilen_tc].index[0]
            
            st.markdown("**Skorlama İçin Kritik Parametreler**")
            col1, col2 = st.columns(2)
            bun = col1.number_input("BUN (mg/dL)", value=get_val(df, idx, "BUN"))
            wbc = col2.number_input("WBC (Lökosit) /mm³", value=get_val(df, idx, "WBC"))
            
            st.markdown("**Biyokimya ve Hemogram**")
            l_col1, l_col2, l_col3, l_col4 = st.columns(4)
            amilaz = l_col1.number_input("Amilaz (U/mL)", value=get_val(df, idx, "Amilaz"))
            lipaz = l_col2.number_input("Lipaz (U/mL)", value=get_val(df, idx, "Lipaz"))
            glukoz = l_col3.number_input("Glukoz (mg/dL)", value=get_val(df, idx, "Glukoz"))
            kreatinin = l_col4.number_input("Kreatinin (mg/dL)", value=get_val(df, idx, "Kreatinin"))
            
            na = l_col1.number_input("Sodyum (Na)", value=get_val(df, idx, "Na"))
            k = l_col2.number_input("Potasyum (K)", value=get_val(df, idx, "K"))
            ast = l_col3.number_input("AST (U/L)", value=get_val(df, idx, "AST"))
            alt = l_col4.number_input("ALT (U/L)", value=get_val(df, idx, "ALT"))
            
            bilirubin = l_col1.number_input("T. Bilirubin", value=get_val(df, idx, "Bilirubin"))
            albumin = l_col2.number_input("Albümin (g/dL)", value=get_val(df, idx, "Albumin"))
            htc = l_col3.number_input("Hematokrit (%)", value=get_val(df, idx, "Htc"))
            hgb = l_col4.number_input("Hemoglobin", value=get_val(df, idx, "Hgb"))
            
            st.markdown("**Kan Gazı ve Diğerleri**")
            kg_col1, kg_col2, kg_col3, kg_col4 = st.columns(4)
            plt = kg_col1.number_input("Trombosit", value=get_val(df, idx, "Plt"))
            laktat = kg_col2.number_input("Laktat", value=get_val(df, idx, "Laktat"))
            ph = kg_col3.number_input("Arteriyel pH", value=get_val(df, idx, "pH"))
            paco2 = kg_col4.number_input("PaCO2", value=get_val(df, idx, "PaCO2"))
            pao2 = kg_col1.number_input("PaO2", value=get_val(df, idx, "PaO2"))
            hco3 = kg_col2.number_input("HCO3", value=get_val(df, idx, "HCO3"))
            
            if st.button("Lab Sonuçlarını Kaydet ve Skorları Hesapla"):
                df.at[idx, "BUN"] = bun; df.at[idx, "WBC"] = wbc; df.at[idx, "Amilaz"] = amilaz
                df.at[idx, "Lipaz"] = lipaz; df.at[idx, "Glukoz"] = glukoz; df.at[idx, "Kreatinin"] = kreatinin
                df.at[idx, "Na"] = na; df.at[idx, "K"] = k; df.at[idx, "AST"] = ast; df.at[idx, "ALT"] = alt
                df.at[idx, "Bilirubin"] = bilirubin; df.at[idx, "Albumin"] = albumin; df.at[idx, "Htc"] = htc
                df.at[idx, "Hgb"] = hgb; df.at[idx, "Plt"] = plt; df.at[idx, "Laktat"] = laktat
                df.at[idx, "pH"] = ph; df.at[idx, "PaCO2"] = paco2; df.at[idx, "PaO2"] = pao2; df.at[idx, "HCO3"] = hco3
                
                h = df.loc[idx]
                sirs = sirs_hesapla(h["Ates"], h["Nabiz"], h["Solunum"], wbc)
                bisap = bisap_hesapla(bun, h["GKS"], sirs, h["Yas"], h["Plevral_Efuzyon"])
                
                df.at[idx, "SIRS_Skoru"] = sirs
                df.at[idx, "BISAP_Skoru"] = bisap
                veri_kaydet(df)
                st.success(f"Lab verileri Google'a eklendi! SIRS: {sirs}, BISAP: {bisap}")

    with sekme3:
        st.subheader("Hastane Yatışı ve Sonlanım Bilgileri")
        hasta_secim_son = st.selectbox("Sonlanım İçin Hasta Seçin", df["TC_No"] + " - " + df["Ad_Soyad"] if not df.empty else ["Hasta Yok"], key="son_secim")
        
        if not df.empty and hasta_secim_son != "Hasta Yok":
            secilen_tc_son = hasta_secim_son.split(" - ")[0]
            idx_son = df[df["TC_No"] == secilen_tc_son].index[0]
            
            st.markdown("**Revize Atlanta Sınıflaması**")
            atlanta_opts = ["Belirtilmedi", "Hafif (Organ yetmezliği yok)", "Orta Şiddette (<48 saat yetmezlik)", "Ağır (Kalıcı yetmezlik >=48 saat)"]
            mevcut_atlanta = df.at[idx_son, "Atlanta"] if pd.notna(df.at[idx_son, "Atlanta"]) and df.at[idx_son, "Atlanta"] != "" else "Belirtilmedi"
            atlanta = st.selectbox("Şiddet", atlanta_opts, index=atlanta_opts.index(mevcut_atlanta) if mevcut_atlanta in atlanta_opts else 0)
            
            st.markdown("**Yatış Bilgileri**")
            s_col1, s_col2 = st.columns(2)
            yatis_karari = s_col1.radio("Yatış Kararı", ["Belirtilmedi", "Yatış", "Taburcu"])
            yatis_yeri = s_col2.selectbox("Yatış Yeri", ["Belirtilmedi", "Servis", "Yoğun Bakım"])
            
            ybu_sure = s_col1.number_input("YBÜ Kalış Süresi (Gün)", min_value=0, value=int(get_val(df, idx_son, "YBU_Sure")))
            toplam_sure = s_col2.number_input("Toplam Hastane Kalış Süresi (Gün)", min_value=0, value=int(get_val(df, idx_son, "Toplam_Sure")))
            
            st.markdown("**Komplikasyon ve Sonlanım**")
            lokal_komp = st.selectbox("Lokal Komplikasyonlar", ["Yok", "Nekroz", "Apse", "Psödokist", "Ekstrapankreatik Koleksiyon"])
            mudahale = st.radio("Cerrahi/Girişimsel Müdahale", ["Hayır", "Evet"])
            mortalite = st.radio("Hastanede Kalış Süresi Sonlanım", ["Belirtilmedi", "Taburcu", "In-Hospital Mortalite"])
            
            if st.button("Sonlanım Verilerini Kaydet"):
                df.at[idx_son, "Atlanta"] = atlanta
                df.at[idx_son, "Yatis_Karari"] = yatis_karari
                df.at[idx_son, "Yatis_Yeri"] = yatis_yeri
                df.at[idx_son, "YBU_Sure"] = ybu_sure
                df.at[idx_son, "Toplam_Sure"] = toplam_sure
                df.at[idx_son, "Lokal_Komp"] = lokal_komp
                df.at[idx_son, "Mudahale"] = mudahale
                df.at[idx_son, "Mortalite"] = mortalite
                veri_kaydet(df)
                st.success("Sonlanım bilgileri Google'a kaydedildi!")

# --- RADYOLOG EKRANI ---
elif st.session_state.kullanici_rolu == "Radyolog":
    st.title("☢️ Radyoloji Paneli")
    if st.button("Çıkış Yap"):
        st.session_state.kullanici_rolu = None
        st.rerun()
        
    df = veri_yukle()
    
    st.subheader("Radyoloji Puanlaması Bekleyen Hastalar")
    hasta_secim = st.selectbox("İncelenecek Hastayı Seçin", df["TC_No"] + " - " + df["Ad_Soyad"] if not df.empty else ["Hasta Yok"])
    
    if not df.empty and hasta_secim != "Hasta Yok":
        st.write("Lütfen aşağıdaki bulguları işaretleyin. Puanlar otomatik hesaplanacaktır.")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**CTSI (Balthazar) Değerlendirmesi**")
            balthazar = st.selectbox("Pankreas Morfolojisi", ["Grade A (0 Puan)", "Grade B (1 Puan)", "Grade C (2 Puan)", "Grade D (3 Puan)", "Grade E (4 Puan)"])
            nekroz_ctsi = st.selectbox("Nekroz Yüzdesi", ["Yok (0 Puan)", "<%33 (2 Puan)", "%33-%50 (4 Puan)", ">%50 (6 Puan)"])
        
        with col2:
            st.markdown("**MCTSI (Modifiye) Değerlendirmesi**")
            inflamasyon = st.selectbox("İnflamasyon", ["Normal (0 Puan)", "Fokal/Diffüz Genişleme (2 Puan)", "Peripankreatik Sıvı (4 Puan)"])
            nekroz_mctsi = st.selectbox("MCTSI Nekroz", ["Yok (0 Puan)", "<%30 (2 Puan)", ">%30 (4 Puan)"])
            komplikasyon = st.radio("Ekstrapankreatik Komplikasyon", ["Yok (0 Puan)", "Var (2 Puan)"])
            
        if st.button("Radyoloji Skorlarını Kaydet"):
            ctsi_puan = int(balthazar.split("(")[1][0]) + int(nekroz_ctsi.split("(")[1][0])
            mctsi_puan = int(inflamasyon.split("(")[1][0]) + int(nekroz_mctsi.split("(")[1][0]) + int(komplikasyon.split("(")[1][0])
            
            secilen_tc = hasta_secim.split(" - ")[0]
            hasta_idx = df[df["TC_No"] == secilen_tc].index[0]
            
            df.at[hasta_idx, "CTSI_Skoru"] = ctsi_puan
            df.at[hasta_idx, "MCTSI_Skoru"] = mctsi_puan
            veri_kaydet(df)
            
            st.success(f"Başarılı! CTSI Toplam: {ctsi_puan}, MCTSI Toplam: {mctsi_puan} (Google'a İşlendi)")
