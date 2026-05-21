# Orbit Wars - Optimus Prime Auto-Iteration System

Bu proje, Kaggle Orbit Wars yarışması için geliştirilmiş, **kendi kendini eğiten ve evrimleşen (Genetic Algorithm)** bir yapay zeka sistemidir.

## 🧠 Mimari (Nasıl Çalışıyor?)

Sistem iki ana parçadan oluşur: **Modüler Strateji Beyni** ve **Evrim Motoru**.

### 1. Modüler Strateji Beyni (`bot/` klasörü)
Ajanın savaş sırasında kullandığı tüm zeka buradadır. Tek bir devasa dosya yerine, rahat geliştirilebilmesi için modüllere bölünmüştür:
- `geometry.py`: Vektör matematiği, güneşe çarpma hesaplamaları ve hareketli gezegenleri (orbit) önceden tahmin edip vurma (leading target) yeteneği.
- `state.py`: Düşman filolarının rotasını hesaplayıp bizim gezegenlerimize gelen bir tehdit olup olmadığını anlayan (threat detection) ve oyunun hangi fazında (early/mid/late) olduğumuzu bulan modül.
- `scoring.py`: Hedef gezegenlerin değerini, üretim hızını ve mesafesini hesaplayıp bir "fırsat skoru" çıkaran modül.
- `strategy.py`: Ana karar mekanizması. Şartları değerlendirir ve filoları yola çıkarır.
- `params.py`: Evrim motorundan gelen 16 temel parametreyi alıp, oyunun 3 fazı için (toplam 48+) dinamik parametre setlerine çeviren akıllı dönüştürücü.

### 2. Evrim Motoru (`tools/` klasörü)
Yazdığımız bu kusursuz beynin "katsayılarını" (ne kadar agresif olmalı, kaç gemi yedeklemeli vb.) milyonlarca ihtimal arasından optimize eden otomasyon sistemidir.
- `generate_agents.py`: `bot/` klasöründeki dosyaları okur ve bunları tek bir Python dosyası olarak (Şablon) birleştirir.
- `auto_iterate.py`: Bu şablonu alır, parametrelerini rastgele (mutasyon) değiştirerek yüzlerce ajan üretir. Bunları kendi aralarında savaştırır.

## 🧬 Genetik Algoritma & Seçkinler Havuzu (Elitism)

Sistem bir sonraki nesil (round) mutantları üretirken sıfırdan başlamaz. Şu 4 ana kaynaktan DNA alır:
1. **Şampiyon Şablonu:** Şu ana kadar submit edilmiş en iyi ajanın DNA'sı (Sistem bunu %60-70 ağırlıkla seçer).
2. **Elite Havuzu (`elite_pool.json`):** Şampiyon olamasa bile %50'nin üzerinde kazanma oranı elde etmiş en yetenekli 50 ajanın başarılı parametreleri.
3. **Kaggle Ustaları (`replay_signals.json`):** Kaggle liderlik tablosundaki en iyi gerçek oyuncuların maçlarından çekilmiş oyun tarzı istatistikleri.
4. **Temel Şablonlar:** Sistemi başlatmak için oluşturulmuş agresif, defansif, ekonomist gibi kök DNA'lar.

Evrim motoru bu DNA'ları alır, parametrelerini milimetrik olarak mutasyona uğratır ve hayatta kalanları yeni şampiyon ilan eder. Bu döngü sonsuza kadar devam eder.

## 🚀 Nasıl Kullanılır?

### Ana Eğitim Döngüsünü Başlatmak
Sistemi 6 çekirdekli asenkron modda başlatıp elitleri üretmesi için:
```bash
./run_v3_loop.sh
```
*(Döngüyü `Ctrl+C` ile istediğiniz zaman durdurabilirsiniz. Durum `auto_runs/state.json` içine otomatik kaydedilir, tekrar başlattığınızda kaldığı yerden ve en son şampiyonun DNA'sından devam eder.)*

### Kaggle Kayıtlarını Güncellemek
Dünyadaki en iyi botların yeni taktiklerini sisteme yedirmek için (ana döngüyü durdurmanıza gerek yoktur, ayrı bir terminalden yapılabilir):
```bash
python tools/fetch_kaggle_replays.py
python tools/replay_intake.py
```

## 🛠️ Manuel Geliştirme (Biz Ne Yapacağız?)
Algoritma sadece "Sayıları" optimize eder. Yeni bir oyun mekaniği (örneğin "Müttefik gezegenlerden takviye isteme" zekası) eklemek istediğimizde:
1. `./run_v3_loop.sh` döngüsünü durdur.
2. `bot/` klasöründeki ilgili modüle yeni Python kodunu/mantığını yaz.
3. `./run_v3_loop.sh`'i tekrar başlat. Evrim motoru yazdığın yeni mantığı otomatik derleyip kendi içinde test edip yeni katsayıları bulmaya başlayacaktır.
