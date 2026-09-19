# Chibi Crosshair Studio

Windows imleçlerini karakter PNG'leriyle değiştiren ve nişangâh gösteren uygulama. `Chibi Simge Güncelleyici.exe`, GitHub'dan yeni PNG'leri indirip mevcut uygulamaya uygular. Yeni simgeler için ana uygulamanın EXE dosyasını tekrar indirmek gerekmez.

GitHub deposu: https://github.com/novax1213/chibi-crosshair-studio

## Kullanıcı için

1. GitHub Releases bölümündeki `Chibi-Crosshair-Studio-Windows.zip` dosyasını indirin; içindeki iki EXE'yi **aynı klasöre** çıkarın.
2. Ana uygulamada **Yeni simgeleri indir** düğmesine basın. Güncelleyici doğrudan da açılabilir.
3. Güncelleyici bu GitHub depo adresiyle hazır gelir. İsterseniz başka bir açık depo veya doğrudan HTTPS `icons.json` adresi de girebilirsiniz.
4. **Katalogu kontrol et** düğmesi yeni simgeleri listeler. Bir simge ve Windows imleç türü seçip **İndir ve imlece uygula** düğmesine basın.
5. Daha önce seçilmiş bir resmin GitHub'da yeni sürümü varsa **Yüklü simgeleri güncelle** düğmesi onu indirip tekrar uygular.

İndirilen PNG'ler `%LOCALAPPDATA%\ChibiCrosshairStudio\icons` klasöründe tutulur. İnternet bağlantısı kesilse bile seçilen simgeler çalışır. Ana uygulama açıldığında bu dosyaları kullanır; dosya yoksa kendi içindeki resme döner.

## GitHub'a simge ekleme

Depoda `assets/`, `icons.json` ve `build_icon_catalog.py` bulunmalı. Yeni bir PNG'yi `assets/` klasörüne ekleyin. Dosya adında Latin harfleri, rakam, `_` ve `-` kullanın. Aynı adlı PNG değiştirilirse güncelleyici SHA-256 değeriyle değişikliği algılar.

Katalogu yerel bilgisayarda üretmek için:

```powershell
python build_icon_catalog.py
```

Ardından PNG'leri ve güncellenen `icons.json` dosyasını GitHub'a gönderin. Depodaki `.github/workflows/icon-catalog.yml` iş akışı da `assets/` değişikliklerinden sonra katalogu üretip commit etmeyi dener. Bunun için GitHub Actions'ın depoya yazma izni olmalı; iş akışı çalışmazsa yukarıdaki komutu kullanıp `icons.json` dosyasını elle gönderin.

`icons.json` içindeki her kayıt şu alanları içerir:

```json
{
  "id": "YeniPoz",
  "name": "YeniPoz",
  "file": "assets/YeniPoz.png",
  "sha256": "PNG dosyasının 64 karakterlik SHA-256 değeri",
  "role": "Normal"
}
```

`role`, güncelleyicide başlangıçta seçilecek Windows imleç türüdür. Kullanıcı bunu değiştirebilir. Windows'un 17 sistem imleç türü vardır; katalogda 500'e kadar alternatif PNG bulunabilir.

## Yayınlama ve güncelleme

`assets/`, `icons.json`, kaynak kod ve `.github/workflows/` depoda tutulur. `build/`, `Release/`, yerel hazırlık betikleri ve ZIP dosyası Git deposuna girmez. İlk Windows paketi [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository) bölümünde `Chibi-Crosshair-Studio-Windows.zip` olarak yayınlanır.

Güncelleyici bu deponun adresini varsayılan olarak kullanır; kullanıcı adresi değiştirirse yeni değeri kendi bilgisayarında saklar. Yeni PNG'ler için sürüm paketini yenilemek gerekmez; `assets/` ve `icons.json` güncel olmalıdır.

Ana uygulama değiştiğinde GitHub **Actions → Build Windows package → Run workflow** ile iki EXE içeren yeni ZIP paketini üretebilirsiniz. Bu iş akışı paketi Actions çıktısı olarak verir; GitHub Releases'a hangi sürümü yayınlayacağınıza siz karar verirsiniz.

## Geliştirme

Python, Pillow ve PyInstaller ile iki EXE oluşturulur:

```powershell
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --onefile --windowed --name "Chibi Crosshair Studio" --add-data "assets;assets" --icon app.ico --distpath Release --workpath build app.pyw
python -m PyInstaller --noconfirm --onefile --windowed --name "Chibi Simge Güncelleyici" --icon app.ico --distpath Release --workpath build icon_manager.pyw
```

Uygulama Windows'a özeldir. Nişangâh masaüstü katmanı olarak çizilir; bazı tam ekran oyunlar bu katmanı göstermez.
