# pyright: reportMissingImports=false
from pathlib import Path
import sqlite3

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()
DB_PATH = Path(__file__).with_name("kuponlar.db")


def baglan():
    return sqlite3.connect(DB_PATH)


def tablo_olustur():
    baglanti = baglan()
    try:
        cursor = baglanti.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kuponlar (
                id INTEGER PRIMARY KEY,
                kod TEXT UNIQUE,
                indirim INTEGER,
                kullanim_limiti INTEGER,
                kullanim INTEGER,
                aktif BOOLEAN
            )
        """)
        baglanti.commit()
    finally:
        baglanti.close()


tablo_olustur()


class Kupon(BaseModel):
    isim: str
    aktif: bool = True
    oran: float
    limit: int = 100


@app.get("/")
def root():
    return {"message": "Hello World"}


@app.get("/kuponlar")
def kuponlari_listele():
    baglanti = baglan()
    try:
        cursor = baglanti.cursor()
        cursor.execute("SELECT * FROM kuponlar")
        sonuclar = cursor.fetchall()
        return {"kuponlar": sonuclar}
    finally:
        baglanti.close()


@app.get("/kuponlar/{item_id}")
def read_item(item_id: str):
    baglanti = baglan()
    try:
        cursor = baglanti.cursor()
        cursor.execute(
            "SELECT indirim FROM kuponlar WHERE kod = ?",
            (item_id.upper(),)
        )
        sonuc = cursor.fetchone()
        if sonuc is None:
            raise HTTPException(status_code=404, detail="Kupon Bulunamadı")
        return {"kod": item_id.upper(), "indirim": sonuc[0]}
    finally:
        baglanti.close()


@app.post("/kuponlar/yeni", status_code=201)
def kupon_olustur(item: Kupon):
    baglanti = baglan()
    try:
        cursor = baglanti.cursor()
        cursor.execute(
            "SELECT indirim FROM kuponlar WHERE kod = ?",
            (item.isim.upper(),)
        )
        sonuc = cursor.fetchone()
        if sonuc is not None:
            raise HTTPException(status_code=409, detail="Bu kupon mevcut")
        if item.oran <= 0 or item.oran > 100:
            raise HTTPException(status_code=400, detail="Geçersiz Oran Girildi")
        if item.limit <= 0:
            raise HTTPException(status_code=400, detail="Kullanım limiti 0'dan büyük olmalı")
        
        cursor.execute(
            """INSERT INTO kuponlar (kod, indirim, kullanim_limiti, kullanim, aktif)
               VALUES (?, ?, ?, ?, ?)""",
            (item.isim.upper(), item.oran, item.limit, 0, item.aktif)
        )
        baglanti.commit()
        return {"Mesaj": "Kod Başarıyla Oluşturuldu"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Bu kupon mevcut")
    finally:
        baglanti.close()


@app.delete("/kupon/{item}")
def kupon_sil(item: str):
    baglanti = baglan()
    try:
        cursor = baglanti.cursor()
        cursor.execute("SELECT kod FROM kuponlar WHERE kod = ?", (item.upper(),))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Kupon Bulunamadı")
        cursor.execute("DELETE FROM kuponlar WHERE kod = ?", (item.upper(),))
        baglanti.commit()
        return {"Kupon": "Başarıyla silindi"}
    finally:
        baglanti.close()


@app.patch("/kupon/{item}")
def kupon_durum(item: str):
    baglanti = baglan()
    try:
        cursor = baglanti.cursor()
        cursor.execute("SELECT aktif FROM kuponlar WHERE kod = ?", (item.upper(),))
        sonuc = cursor.fetchone()
        if sonuc is None:
            raise HTTPException(status_code=404, detail="Kupon Bulunamadı")

        yeni_durum = not bool(sonuc[0])
        cursor.execute(
            "UPDATE kuponlar SET aktif = ? WHERE kod = ?",
            (yeni_durum, item.upper())
        )
        baglanti.commit()
        if yeni_durum:
            return {"Mesaj": "Kupon Aktif olarak Ayarlandı"}
        return {"Mesaj": "Kupon Pasif olarak Ayarlandı"}
    finally:
        baglanti.close()


@app.get("/hesapla/{miktar}/{item}")
def hesapla(miktar: int, item: str):
    if miktar < 0:
        raise HTTPException(status_code=400, detail="Geçersiz fiyat Girildi")

    baglanti = baglan()
    try:
        cursor = baglanti.cursor()
        cursor.execute(
            "SELECT indirim, aktif FROM kuponlar WHERE kod = ?",
            (item.upper(),)
        )
        sonuc = cursor.fetchone()
        if sonuc is None:
            raise HTTPException(status_code=404, detail="Kupon Bulunamadı")
        if not sonuc[1]:
            raise HTTPException(status_code=400, detail="Kupon Aktif değil!")

        oran = sonuc[0]
        indirim_tutari = miktar * (oran / 100)
        son_fiyat = miktar - indirim_tutari
        return {
            "normal fiyat": miktar,
            "indirim oranı": oran,
            "son fiyat": son_fiyat
        }
    finally:
        baglanti.close()


@app.post("/kupon/kullan/{item}")
def kupon_kullan(item: str):
    baglanti = baglan()
    try:
        cursor = baglanti.cursor()
        cursor.execute(
            "SELECT aktif, kullanim, kullanim_limiti FROM kuponlar WHERE kod = ?",
            (item.upper(),)
        )
        sonuc = cursor.fetchone()
        if sonuc is None:
            raise HTTPException(status_code=404, detail="Kupon Bulunamadı")

        aktif, kullanim, kullanim_limiti = sonuc
        if kullanim >= kullanim_limiti:
            raise HTTPException(status_code=400, detail="Bu kupon limiti doldu")
        if not aktif:
            raise HTTPException(status_code=400, detail="Kupon Aktif değil!")

        # Kullanım artırmayı tek SQL güncellemesiyle yap.
        cursor.execute(
            """UPDATE kuponlar SET kullanim = kullanim + 1
               WHERE kod = ? AND aktif = 1 AND kullanim < kullanim_limiti""",
            (item.upper(),)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=400, detail="Kupon artık kullanılamıyor")
        cursor.execute("SELECT kullanim FROM kuponlar WHERE kod = ?", (item.upper(),))
        deger = cursor.fetchone()[0]
        baglanti.commit()
        return {"Mesaj": "kupon başarıyla Kullanıldı", "Kullanım": deger}
    finally:
        baglanti.close()


@app.get("/istatistikler/kuponlar")
def istatistikler():
    baglanti = baglan()
    try:
        cursor = baglanti.cursor()
        cursor.execute("SELECT kod, indirim, kullanim_limiti, kullanim, aktif FROM kuponlar")
        sonuclar = cursor.fetchall()

        kuponlar2 = {}
        for kod, indirim, limit, kullanim, aktif in sonuclar:
            kuponlar2[kod] = {
                "indirim": indirim,
                "limit": limit,
                "kalan hak": max(0, limit - kullanim),
                "Kullanım": kullanim,
                "Aktif": bool(aktif)
            }
        return {"kuponlar": kuponlar2}
    finally:
        baglanti.close()
@app.patch("/kuponlar/oran/{kod}/{oran}")
async def indirim_guncelle(kod: str, oran: int):
    baglanti = baglan()
    try:
        cursor = baglanti.cursor()
        cursor.execute(
                    "SELECT indirim FROM kuponlar WHERE kod = ?",
                    (kod.upper(),)
                )
        sonuc = cursor.fetchone()
        if sonuc is None:
            raise HTTPException(status_code=404, detail="Kupon Bulunamadı")
        if(oran <= 0 or oran> 100):
            raise HTTPException(status_code=400, detail="geçerli bir oran giriniz!")
        else:
            cursor.execute(
            "UPDATE kuponlar SET indirim = ? WHERE kod = ?",
            (oran, kod.upper())
        )
            baglanti.commit()

            return {
            "Eski Oran":sonuc[0] ,
            "Yeni oran": oran,
        }



    finally:
        baglanti.close()

