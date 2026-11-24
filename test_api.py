# pyright: reportMissingImports=false
import pytest
from fastapi.testclient import TestClient
import main as main3

client = TestClient(main3.app)


@pytest.fixture(autouse=True)
def gecici_veritabani(tmp_path, monkeypatch):
    """Her testi ayrı bir SQLite dosyasıyla çalıştır; gerçek kuponları değiştirme."""
    monkeypatch.setattr(main3, "DB_PATH", tmp_path / "test_kuponlar.db")
    main3.tablo_olustur()


def test_kuponlari_listele():
    response = client.get("/kuponlar")
    assert response.status_code == 200
    assert "kuponlar" in response.json()
    assert response.json()["kuponlar"] == []


def test_istatistikler():
    olustur = client.post("/kuponlar/yeni", json={
        "isim": "TEST",
        "oran": 10,
        "limit": 1,
        "aktif": True,
    })
    assert olustur.status_code == 201

    response = client.get("/istatistikler/kuponlar")
    assert response.status_code == 200
    assert "kuponlar" in response.json()
    assert response.json()["kuponlar"]["TEST"]["kalan hak"] == 1


def test_kupon404():
    response = client.get("/kuponlar/OLMAYAN_KUPON")
    assert response.status_code == 404


def test_kuponyeni():
    response = client.post("/kuponlar/yeni", json={
        "isim": "TEST",
        "oran": 10,
        "limit": 1,
        "aktif": True,
    })
    assert response.status_code == 201

    # POST sadece mesaj döndürüyor; oluşturulan kuponu GET ile kontrol ediyoruz.
    kontrol = client.get("/kuponlar/TEST")
    assert kontrol.status_code == 200
    assert kontrol.json()["indirim"] == 10


def test_kuponkullan():
    olustur = client.post("/kuponlar/yeni", json={
        "isim": "TEST",
        "oran": 10,
        "limit": 1,
        "aktif": True,
    })
    assert olustur.status_code == 201

    once = client.get("/istatistikler/kuponlar").json()["kuponlar"]["TEST"]["Kullanım"]
    response = client.post("/kupon/kullan/TEST")
    sonra = client.get("/istatistikler/kuponlar").json()["kuponlar"]["TEST"]["Kullanım"]

    assert response.status_code == 200
    assert sonra == once + 1
    assert response.json()["Kullanım"] == sonra


def test_kuponkullan2():
    olustur = client.post("/kuponlar/yeni", json={
        "isim": "TEST",
        "oran": 10,
        "limit": 1,
        "aktif": True,
    })
    assert olustur.status_code == 201
    

    ilk_kullanim = client.post("/kupon/kullan/TEST")
    ikinci_kullanim = client.post("/kupon/kullan/TEST")

    assert ilk_kullanim.status_code == 200
    assert ikinci_kullanim.status_code == 400
    assert client.get("/istatistikler/kuponlar").json()["kuponlar"]["TEST"]["Kullanım"] == 1
def test_kuponoran1():
    response = client.post("/kuponlar/yeni", json={
        "isim": "TEST2",
        "oran": 10,
        "limit": 1,
        "aktif": True,
    })
    assert response.status_code == 201
    kontrol = client.get("/kuponlar/TEST2")
    assert kontrol.status_code == 200
    assert kontrol.json()["indirim"] == 10
    dene = client.patch("/kuponlar/oran/TEST2/25")
    assert dene.status_code == 200
    ilk_kullanim = client.post("/kupon/kullan/TEST2")
    assert ilk_kullanim.status_code == 200
    ikinci_kullanim = client.post("/kupon/kullan/TEST2")
    assert ikinci_kullanim.status_code == 400
    kontrol = client.get("/kuponlar/TEST2")
    assert kontrol.status_code == 200
    assert kontrol.json()["indirim"] == 25

