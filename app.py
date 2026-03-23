import streamlit as st
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- AYARLAR VE VERİTABANI ---
st.set_page_config(page_title="Akut Pankreatit Çalışması", layout="wide")

SHEET_URL = "https://docs.google.com/spreadsheets/d/1fTA-MdaaV5CU812aPn1bZZc1KIMWey-P84jAqIbBYOA/edit?gid=0#gid=0"

COLS = [
    "TC_No", "Ad_Soyad", "Kayit_Tarihi", "Kayit_Yapan", "Lab_Yapan", "Yatis_Yapan", "Radyoloji_Yapan",
    "Yas", "Cinsiyet", "Etiyoloji", "Semptom_Suresi", "GKS", 
    "Ates", "Nabiz", "Solunum", "Sistolik", "Diyastolik", "SpO2", "Plevral_Efuzyon", 
    "BUN", "WBC", "Amilaz", "Lipaz", "Glukoz", "Kreatinin", "Na", "K", "AST", "ALT", 
    "Bilirubin", "Albumin", "Htc", "Hgb", "Plt", "Laktat", "pH", "PaCO2", "PaO2", "HCO3", 
    "Atlanta", "Yatis_Karari", "Yatis_Yeri", "YBU_Sure", "Toplam_Sure", "Lokal_Komp", 
    "Mudahale", "Mortalite", "SIRS_Skoru", "BISAP_Skoru", "CTSI_Skoru", "MCTSI_Skoru",
    "Rad_Balthazar", "Rad_Nekroz_CTSI", "Rad_Inflamasyon", "Rad_Nekroz_MCTSI", "Rad_Ekstra_Komp"
]

@st.cache_resource
def get_gspread_client():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

@st.cache_data(ttl=30)
def veri_yukle():
    client = get_gspread_client()
    sheet = client.open_by_url(SHEET_URL).sheet1
    data = sheet.get_all_values()
    if not data:
        sheet.update(values=[COLS], range_name='A1')
        return pd.DataFrame(columns=COLS)
    
    headers = data.pop(0)
    df = pd.DataFrame(data, columns=headers)
    
    for col in COLS:
        if col not in df.columns:
            df[col] = ""
            
    if 'TC_No' in df.columns:
        df['TC_No'] = df['TC_No'].astype(str)
    return df

def veri_kaydet(df):
    client = get_gspread_client()
    sheet = client.open_by_url(SHEET_URL).sheet1
    sheet.clear()
    sheet.update(values=[df.columns.values.tolist()] + df.values.tolist(), range_name='A1')
    veri_yukle.clear()

def get_val(df, idx, col, default=0.0):
    val = df.at[idx, col]
    if pd.isna(val) or str(val).strip() == "":
        return default
    try:
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
        if str(plevral).strip() == "Var": skor += 1
    except:
        pass
    return skor

# --- GİRİŞ PANELİ (LOGIN) ---
if "kullanici_rolu" not in st.session_state:
    st.session_state.kullanici_rolu = None
    st.session_state.aktif_kullanici = None

if st.session_state.kullanici_rolu is None:
    st.title("🏥 Akut Pankreatit Çalışması Portalı")
    st.write("Lütfen giriş yapınız.")
    
    kullanici_adi = st.text_input("Kullanıcı Adı").strip().lower()
    sifre = st.text_input("Şifre", type="password")
    
    if st.button("Giriş Yap"):
        if kullanici_adi in ["acil", "gulsima", "emir", "oyku"] and sifre == "0322":
            st.session_state.kullanici_rolu = "Acil Hekimi"
            st.session_state.aktif_kullanici = kullanici_adi.capitalize()
            st.rerun()
        elif kullanici_adi == "radyolog" and sifre == "1230":
            st.session_state.kullanici_rolu = "Radyolog"
            st.session_state.aktif_kullanici = "Radyolog"
            st.rerun()
        else:
            st.error("Hatalı kullanıcı adı veya şifre!")

# --- ACİL HEKİMİ EKRANI ---
elif st.session_state.kullanici_rolu == "Acil Hekimi":
    st.title(f"👨‍⚕️ Acil Paneli - Hoş Geldin {st.session_state.aktif_kullanici}")
    if st.button("Çıkış Yap"):
        st.session_state.kullanici_rolu = None
        st.session_state.aktif_kullanici = None
        st.rerun()
        
    sekme1, sekme2, sekme3, sekme4 = st.tabs(["📋 Yeni Hasta Kaydı", "🔬 Laboratuvar Girişi", "🏥 Yatış ve Sonlanım", "📊 Hasta Listesi ve Düzenleme"])
    
    df = veri_yukle()
    
    # SEKME 1: YENİ HASTA KAYDI
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
        
        # Plevral Efüzyon buradan kaldırıldı, 3 sütuna düşürüldü
        v5, v6, v7 = st.columns(3)
        sistolik = v5.number_input("Sistolik KB", value=120)
        diyastolik = v6.number_input("Diyastolik KB", value=80)
        gks = v7.selectbox("Glasgow Koma Skoru", range(3, 16), index=12)
        
        if st.button("Hastayı Kaydet"):
            if len(tc) == 11 and ad:
                bugun = datetime.now().strftime("%d/%m/%Y")
                yeni_veri = {col: "" for col in COLS}
                yeni_veri.update({
                    "TC_No": str(tc), "Ad_Soyad": ad, "Kayit_Tarihi": bugun, 
                    "Kayit_Yapan": st.session_state.aktif_kullanici,
                    "Yas": yas, "Cinsiyet": cinsiyet, "Etiyoloji": etiyoloji,
                    "Semptom_Suresi": semptom, "GKS": gks, "Ates": ates, "Nabiz": nabiz, "Solunum": solunum,
                    "Sistolik": sistolik, "Diyastolik": diyastolik, "SpO2": spo2, "Plevral_Efuzyon": "Yok" # Standart boş değer
                })
                df = pd.concat([df, pd.DataFrame([yeni_veri])], ignore_index=True)
                veri_kaydet(df)
                st.success(f"Hasta başarıyla kaydedildi! (Kaydeden: {st.session_state.aktif_kullanici})")
            else:
                st.error("Lütfen TC (11 hane) ve Ad Soyad alanlarını doldurun.")

    # SEKME 2: LABORATUVAR
    with sekme2:
        st.subheader("Laboratuvar Sonuçlarını İşle")
        arama_lab = st.text_input("🔍 İsim veya TC'nin bir kısmını yazarak arayın:", key="ara_lab")
        if arama_lab:
            mask_lab = df["TC_No"].str.contains(arama_lab, case=False, na=False) | df["Ad_Soyad"].str.contains(arama_lab, case=False, na=False)
            filtreli_df_lab = df[mask_lab]
        else:
            filtreli_df_lab = df
            
        hasta_listesi_lab = filtreli_df_lab["TC_No"] + " - " + filtreli_df_lab["Ad_Soyad"] if not filtreli_df_lab.empty else ["Hasta Yok"]
        hasta_secim = st.selectbox("Lab İçin Hasta Seçin", hasta_listesi_lab, key="lab_secim_kutu")
        
        if not filtreli_df_lab.empty and hasta_secim != "Hasta Yok":
            secilen_tc = hasta_secim.split(" - ")[0]
            idx = df[df["TC_No"] == secilen_tc].index[0]
            
            st.markdown("**Skorlama İçin Kritik Parametreler**")
            col1, col2, col3 = st.columns(3)
            bun = col1.number_input("BUN (mg/dL)", value=get_val(df, idx, "BUN"))
            wbc = col2.number_input("WBC (Lökosit) /mm³", value=get_val(df, idx, "WBC"))
            
            # Plevral Efüzyon buraya eklendi
            mevcut_plevral = str(df.at[idx, "Plevral_Efuzyon"]).strip()
            plevral_idx = 1 if mevcut_plevral == "Var" else 0
            plevral = col3.radio("Plevral Efüzyon", ["Yok", "Var"], index=plevral_idx)
            
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
            
            if st.button("Lab Sonuçlarını Kaydet"):
                df.at[idx, "BUN"] = bun; df.at[idx, "WBC"] = wbc; df.at[idx, "Amilaz"] = amilaz
                df.at[idx, "Lipaz"] = lipaz; df.at[idx, "Glukoz"] = glukoz; df.at[idx, "Kreatinin"] = kreatinin
                df.at[idx, "Na"] = na; df.at[idx, "K"] = k; df.at[idx, "AST"] = ast; df.at[idx, "ALT"] = alt
                df.at[idx, "Bilirubin"] = bilirubin; df.at[idx, "Albumin"] = albumin; df.at[idx, "Htc"] = htc
                df.at[idx, "Hgb"] = hgb; df.at[idx, "Plt"] = plt; df.at[idx, "Laktat"] = laktat
                df.at[idx, "pH"] = ph; df.at[idx, "PaCO2"] = paco2; df.at[idx, "PaO2"] = pao2; df.at[idx, "HCO3"] = hco3
                df.at[idx, "Plevral_Efuzyon"] = plevral
                df.at[idx, "Lab_Yapan"] = st.session_state.aktif_kullanici
                
                h = df.loc[idx]
                sirs = sirs_hesapla(h["Ates"], h["Nabiz"], h["Solunum"], wbc)
                bisap = bisap_hesapla(bun, h["GKS"], sirs, h["Yas"], plevral)
                
                df.at[idx, "SIRS_Skoru"] = sirs
                df.at[idx, "BISAP_Skoru"] = bisap
                veri_kaydet(df)
                st.success(f"Veriler Google'a eklendi! İşlemi Yapan: {st.session_state.aktif_kullanici}")

    # SEKME 3: YATIŞ
    with sekme3:
        st.subheader("Hastane Yatışı ve Sonlanım Bilgileri")
        arama_son = st.text_input("🔍 İsim veya TC'nin bir kısmını yazarak arayın:", key="ara_son")
        if arama_son:
            mask_son = df["TC_No"].str.contains(arama_son, case=False, na=False) | df["Ad_Soyad"].str.contains(arama_son, case=False, na=False)
            filtreli_df_son = df[mask_son]
        else:
            filtreli_df_son = df
            
        hasta_listesi_son = filtreli_df_son["TC_No"] + " - " + filtreli_df_son["Ad_Soyad"] if not filtreli_df_son.empty else ["Hasta Yok"]
        hasta_secim_son = st.selectbox("Sonlanım İçin Hasta Seçin", hasta_listesi_son, key="son_secim_kutu")
        
        if not filtreli_df_son.empty and hasta_secim_son != "Hasta Yok":
            secilen_tc_son = hasta_secim_son.split(" - ")[0]
            idx_son = df[df["TC_No"] == secilen_tc_son].index[0]
            
            atlanta_opts = ["Belirtilmedi", "Hafif (Organ yetmezliği yok)", "Orta Şiddette (<48 saat yetmezlik)", "Ağır (Kalıcı yetmezlik >=48 saat)"]
            mevcut_atlanta = df.at[idx_son, "Atlanta"] if pd.notna(df.at[idx_son, "Atlanta"]) and df.at[idx_son, "Atlanta"] != "" else "Belirtilmedi"
            atlanta = st.selectbox("Şiddet", atlanta_opts, index=atlanta_opts.index(mevcut_atlanta) if mevcut_atlanta in atlanta_opts else 0)
            
            s_col1, s_col2 = st.columns(2)
            yatis_karari = s_col1.radio("Yatış Kararı", ["Belirtilmedi", "Yatış", "Taburcu"])
            yatis_yeri = s_col2.selectbox("Yatış Yeri", ["Belirtilmedi", "Servis", "Yoğun Bakım"])
            
            ybu_sure = s_col1.number_input("YBÜ Kalış Süresi (Gün)", min_value=0, value=int(get_val(df, idx_son, "YBU_Sure")))
            toplam_sure = s_col2.number_input("Toplam Hastane Kalış Süresi (Gün)", min_value=0, value=int(get_val(df, idx_son, "Toplam_Sure")))
            
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
                df.at[idx_son, "Yatis_Yapan"] = st.session_state.aktif_kullanici
                veri_kaydet(df)
                st.success("Sonlanım bilgileri Google'a kaydedildi!")

    # SEKME 4: HASTA LİSTESİ VE DÜZENLEME
    with sekme4:
        st.subheader("✏️ Tüm Verileri Düzenle (Hızlı Excel Modu)")
        st.info("💡 Aşağıdaki tabloda herhangi bir hücrenin üzerine çift tıklayarak veriyi doğrudan değiştirebilirsiniz.")
        
        edited_df = st.data_editor(df, key="veri_editoru", use_container_width=True, hide_index=True)

        if st.button("💾 Tablodaki Değişiklikleri Google'a Kaydet"):
            for i, row in edited_df.iterrows():
                sirs = sirs_hesapla(row["Ates"], row["Nabiz"], row["Solunum"], row["WBC"])
                edited_df.at[i, "SIRS_Skoru"] = sirs
                edited_df.at[i, "BISAP_Skoru"] = bisap_hesapla(row["BUN"], row["GKS"], sirs, row["Yas"], row["Plevral_Efuzyon"])
            
            veri_kaydet(edited_df)
            st.success("Tüm düzenlemeler başarıyla güncellendi!")

        st.write("---")
        st.subheader("📌 Eksik Veri Takip Listesi")
        
        if df.empty:
            st.info("Henüz sisteme kayıtlı hasta bulunmuyor.")
        else:
            # Çok daha kompakt ve küçük bir mini tablo oluşturuluyor
            durum_listesi = []
            for idx, row in df.iterrows():
                tc = str(row.get("TC_No", ""))
                ad = str(row.get("Ad_Soyad", ""))
                tarih = str(row.get("Kayit_Tarihi", "Tarih Yok"))
                if tarih == "nan" or tarih.strip() == "": tarih = "Tarih Yok"

                lab_ok = str(row.get("BUN", "")).strip() not in ["", "nan"]
                yatis_ok = str(row.get("Atlanta", "")).strip() not in ["", "Belirtilmedi", "nan"]
                rad_ok = str(row.get("CTSI_Skoru", "")).strip() not in ["", "nan"]

                durum_listesi.append({
                    "TC Kimlik": tc,
                    "Ad Soyad": ad,
                    "Kayıt Tarihi": tarih,
                    "Lab": "🟢" if lab_ok else "🔴",
                    "Yatış": "🟢" if yatis_ok else "🔴",
                    "Radyoloji": "🟢" if rad_ok else "🔴"
                })
            
            durum_df = pd.DataFrame(durum_listesi)
            st.dataframe(durum_df, hide_index=True, use_container_width=True)

# --- RADYOLOG EKRANI ---
elif st.session_state.kullanici_rolu == "Radyolog":
    st.title(f"☢️ Radyoloji Paneli - Hoş Geldin {st.session_state.aktif_kullanici}")
    if st.button("Çıkış Yap"):
        st.session_state.kullanici_rolu = None
        st.session_state.aktif_kullanici = None
        st.rerun()
        
    df = veri_yukle()
    
    opt_balthazar = ["Grade A (0 Puan)", "Grade B (1 Puan)", "Grade C (2 Puan)", "Grade D (3 Puan)", "Grade E (4 Puan)"]
    opt_nekroz_c = ["Yok (0 Puan)", "<%33 (2 Puan)", "%33-%50 (4 Puan)", ">%50 (6 Puan)"]
    opt_inf = ["Normal (0 Puan)", "Fokal/Diffüz Genişleme (2 Puan)", "Peripankreatik Sıvı (4 Puan)"]
    opt_nekroz_m = ["Yok (0 Puan)", "<%30 (2 Puan)", ">%30 (4 Puan)"]
    opt_komp = ["Yok (0 Puan)", "Var (2 Puan)"]

    def safe_idx(opts, val):
        return opts.index(val) if pd.notna(val) and val in opts else 0

    sekme_rad1, sekme_rad2 = st.tabs(["📋 Puanlama Bekleyen Hastalar", "✏️ Puanlanmış Hastaları Düzenle"])
    
    with sekme_rad1:
        st.subheader("Henüz Puanlanmamış Hastalar")
        mask_bekleyen = df["CTSI_Skoru"].isna() | (df["CTSI_Skoru"] == "")
        df_bekleyen = df[mask_bekleyen]
        
        arama_rad1 = st.text_input("🔍 İsim veya TC arayın:", key="ara_rad_1")
        if arama_rad1:
            m1 = df_bekleyen["TC_No"].str.contains(arama_rad1, case=False, na=False) | df_bekleyen["Ad_Soyad"].str.contains(arama_rad1, case=False, na=False)
            df_bekleyen = df_bekleyen[m1]
            
        liste_rad1 = df_bekleyen["TC_No"] + " - " + df_bekleyen["Ad_Soyad"] if not df_bekleyen.empty else ["Bekleyen Hasta Yok"]
        secim_rad1 = st.selectbox("İncelenecek Hastayı Seçin", liste_rad1, key="rad_secim_1")
        
        if not df_bekleyen.empty and secim_rad1 != "Bekleyen Hasta Yok":
            secilen_tc1 = secim_rad1.split(" - ")[0]
            idx1 = df[df["TC_No"] == secilen_tc1].index[0]
            
            kayit_tarihi1 = str(df.at[idx1, "Kayit_Tarihi"]) if "Kayit_Tarihi" in df.columns else "Tarih Yok"
            if kayit_tarihi1 == "nan" or kayit_tarihi1.strip() == "": kayit_tarihi1 = "Tarih Yok"
            st.info(f"📅 **Hastanın Sisteme Kayıt Tarihi:** {kayit_tarihi1}")
            
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**CTSI (Balthazar) Değerlendirmesi**")
                balt1 = st.selectbox("Pankreas Morfolojisi", opt_balthazar, key="b1")
                nek_c1 = st.selectbox("Nekroz Yüzdesi", opt_nekroz_c, key="nc1")
            with c2:
                st.markdown("**MCTSI (Modifiye) Değerlendirmesi**")
                inf1 = st.selectbox("İnflamasyon", opt_inf, key="i1")
                nek_m1 = st.selectbox("MCTSI Nekroz", opt_nekroz_m, key="nm1")
                komp1 = st.radio("Ekstrapankreatik Komplikasyon", opt_komp, key="k1")
                
            if st.button("Puanları Kaydet", key="btn1"):
                ctsi_p = int(balt1.split("(")[1][0]) + int(nek_c1.split("(")[1][0])
                mctsi_p = int(inf1.split("(")[1][0]) + int(nek_m1.split("(")[1][0]) + int(komp1.split("(")[1][0])
                
                df.at[idx1, "CTSI_Skoru"] = ctsi_p
                df.at[idx1, "MCTSI_Skoru"] = mctsi_p
                df.at[idx1, "Rad_Balthazar"] = balt1
                df.at[idx1, "Rad_Nekroz_CTSI"] = nek_c1
                df.at[idx1, "Rad_Inflamasyon"] = inf1
                df.at[idx1, "Rad_Nekroz_MCTSI"] = nek_m1
                df.at[idx1, "Rad_Ekstra_Komp"] = komp1
                df.at[idx1, "Radyoloji_Yapan"] = st.session_state.aktif_kullanici
                veri_kaydet(df)
                st.success(f"Başarılı! Bu hasta puanlama listesinden kaldırıldı. CTSI: {ctsi_p}, MCTSI: {mctsi_p}")

    with sekme_rad2:
        st.subheader("Önceden Puanlanmış Hastaları Düzenle")
        mask_tamam = df["CTSI_Skoru"].notna() & (df["CTSI_Skoru"] != "")
        df_tamam = df[mask_tamam]
        
        arama_rad2 = st.text_input("🔍 İsim veya TC arayın:", key="ara_rad_2")
        if arama_rad2:
            m2 = df_tamam["TC_No"].str.contains(arama_rad2, case=False, na=False) | df_tamam["Ad_Soyad"].str.contains(arama_rad2, case=False, na=False)
            df_tamam = df_tamam[m2]
            
        liste_rad2 = df_tamam["TC_No"] + " - " + df_tamam["Ad_Soyad"] if not df_tamam.empty else ["Düzenlenecek Hasta Yok"]
        secim_rad2 = st.selectbox("Düzenlenecek Hastayı Seçin", liste_rad2, key="rad_secim_2")
        
        if not df_tamam.empty and secim_rad2 != "Düzenlenecek Hasta Yok":
            secilen_tc2 = secim_rad2.split(" - ")[0]
            idx2 = df[df["TC_No"] == secilen_tc2].index[0]
            
            eski_ctsi = df.at[idx2, "CTSI_Skoru"]
            eski_mctsi = df.at[idx2, "MCTSI_Skoru"]
            eski_yapan = df.at[idx2, "Radyoloji_Yapan"]
            st.warning(f"⚠️ Bu hasta daha önce puanlanmıştır. Eski Skorlar -> CTSI: {eski_ctsi} | MCTSI: {eski_mctsi} (İşlem Yapan: {eski_yapan})")
            
            c3, c4 = st.columns(2)
            with c3:
                st.markdown("**CTSI (Balthazar) Değerlendirmesi**")
                balt2 = st.selectbox("Pankreas Morfolojisi", opt_balthazar, index=safe_idx(opt_balthazar, df.at[idx2, "Rad_Balthazar"]), key="b2")
                nek_c2 = st.selectbox("Nekroz Yüzdesi", opt_nekroz_c, index=safe_idx(opt_nekroz_c, df.at[idx2, "Rad_Nekroz_CTSI"]), key="nc2")
            with c4:
                st.markdown("**MCTSI (Modifiye) Değerlendirmesi**")
                inf2 = st.selectbox("İnflamasyon", opt_inf, index=safe_idx(opt_inf, df.at[idx2, "Rad_Inflamasyon"]), key="i2")
                nek_m2 = st.selectbox("MCTSI Nekroz", opt_nekroz_m, index=safe_idx(opt_nekroz_m, df.at[idx2, "Rad_Nekroz_MCTSI"]), key="nm2")
                komp2 = st.radio("Ekstrapankreatik Komplikasyon", opt_komp, index=safe_idx(opt_komp, df.at[idx2, "Rad_Ekstra_Komp"]), key="k2")
                
            if st.button("Değişiklikleri Kaydet ve Güncelle", key="btn2"):
                ctsi_p2 = int(balt2.split("(")[1][0]) + int(nek_c2.split("(")[1][0])
                mctsi_p2 = int(inf2.split("(")[1][0]) + int(nek_m2.split("(")[1][0]) + int(komp2.split("(")[1][0])
                
                df.at[idx2, "CTSI_Skoru"] = ctsi_p2
                df.at[idx2, "MCTSI_Skoru"] = mctsi_p2
                df.at[idx2, "Rad_Balthazar"] = balt2
                df.at[idx2, "Rad_Nekroz_CTSI"] = nek_c2
                df.at[idx2, "Rad_Inflamasyon"] = inf2
                df.at[idx2, "Rad_Nekroz_MCTSI"] = nek_m2
                df.at[idx2, "Rad_Ekstra_Komp"] = komp2
                df.at[idx2, "Radyoloji_Yapan"] = f"{st.session_state.aktif_kullanici} (Düzenledi)"
                veri_kaydet(df)
                st.success(f"Güncelleme Başarılı! Yeni Skorlar -> CTSI: {ctsi_p2}, MCTSI: {mctsi_p2}")
