# Chibi Crosshair Studio

Windows imleçlerini karakter PNG'leriyle değiştiren ve nişangâh gösteren uygulama. `Chibi Simge Güncelleyici.exe`, GitHub'dan yeni PNG'leri indirip mevcut uygulamaya uygular. Yeni simgeler için ana uygulamanın EXE dosyasını tekrar indirmek gerekmez.

GitHub deposu: https://github.com/novax1213/chibi-crosshair-studio

## Kullanıcı için

1. GitHub Releases bölümündeki `Chibi-Crosshair-Studio-Windows.zip` dosyasını indirin; içindeki iki EXE'yi **aynı klasöre** çıkarın.
2. Ana uygulamadaki üçüncü **Paketler** sekmesini açın. GitHub'daki paketler otomatik yüklenir; bir paket seçince simge adları ve önizleme görünür.
3. **Paketi indir ve uygula** düğmesiyle paketteki tüm imleçleri indirin ve uygulayın. **Paketleri yenile** ile sonradan eklenen paketleri görebilirsiniz. Ayrı güncelleyici, yeni simge yüklemek veya tek bir imleç uygulamak için de açılabilir.
4. Tek bir poz kullanmak isterseniz paketteki simgeyi ve Windows imleç türünü seçip **İndir ve imlece uygula** düğmesine basın. İsterseniz başka bir açık depo veya doğrudan HTTPS `icons.json` adresi de girebilirsiniz.
5. Daha önce seçilmiş bir resmin GitHub'da yeni sürümü varsa **Yüklü simgeleri güncelle** düğmesi onu indirip tekrar uygular.

İndirilen PNG'ler `%LOCALAPPDATA%\ChibiCrosshairStudio\icons` klasöründe tutulur. İnternet bağlantısı kesilse bile seçilen simgeler çalışır. Ana uygulama açıldığında bu dosyaları kullanır; dosya yoksa kendi içindeki resme döner.

## GitHub'a simge ekleme

Depo sahibi GitHub hesabıyla giriş yapılan bilgisayarda ana uygulamanın **Paketler → Yeni paket ekle** düğmesine basın. PNG resimlerinin olduğu klasörü sürükleyip bırakın veya **Klasör seç** ile gösterin. Ekranda 17 Windows imlecinin adı (`Normal.png`, `Help.png`, `Busy.png` vb.), bulunan dosyalar ve önizleme görünür. Paket adını kontrol edip **Paketi GitHub'a yükle** düğmesine basın. Uygulama yalnızca değişen resimleri `packs/<paket-adı>/` klasörüne gönderir ve `icons.json` kataloğunu yeniler. Kullanıcılar yeni paketi **Paketler** listesinden indirir. Yayınlama düğmeleri diğer hesaplarda görünmez; GitHub yazma yetkisi ayrıca gereklidir.

Yükleme için Git for Windows ve bu depoya yazma yetkisi gerekir. GitHub kimlik doğrulaması bilgisayarda Git için kurulmuş olmalıdır. Program güncel depoyu geçici klasöre otomatik indirir; proje klasörü seçmeniz gerekmez. Dosyaları indiren kullanıcıların Git kurmasına veya yazma yetkisi almasına gerek yoktur.

Klasör seçme ekranı 17 sistem imlecinin adlarını kullanır. Katalogda serbest adlı ek alternatif pozlar yayınlamak isterseniz aşağıdaki elle yöntem kullanılabilir. Depoda `assets/`, `icons.json` ve `build_icon_catalog.py` bulunmalı. Dosya adında Latin harfleri, rakam, `_` ve `-` kullanın.

Katalogu yerel bilgisayarda üretmek için:

```powershell
python build_icon_catalog.py
```

Ardından PNG'leri ve güncellenen `icons.json` dosyasını GitHub'a gönderin:

```powershell
git add assets icons.json
git commit -m "Yeni simgeleri ekle"
git push
```

Depodaki `.github/workflows/icon-catalog.yml` iş akışı da `assets/` değişikliklerinden sonra katalogu üretip commit etmeyi dener. GitHub Actions hesabınızda kullanılamıyorsa veya depoya yazma izni yoksa yukarıdaki yerel komutlar yeterlidir. Kullanıcılar yeni simgeleri yine güncelleyiciyle indirir.

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
python -m PyInstaller --noconfirm --onefile --windowed --name "Chibi Simge Güncelleyici" --icon app.ico --additional-hooks-dir . --distpath Release --workpath build icon_manager.pyw
```

Uygulama Windows'a özeldir. Nişangâh masaüstü katmanı olarak çizilir; bazı tam ekran oyunlar bu katmanı göstermez.
