# e5 vs Gemini embeddings

Real queries: average shared top-5 = 1.2/5

## Paraphrase test (60 queries)

| index | hit@1 | hit@5 | MRR | median top-1 distance |
|---|---|---|---|---|
| e5 | 80% | 93% | 0.848 | 0.123 |
| gemini | 80% | 93% | 0.853 | 0.182 |

Both found within top-5: 53/60

## Threshold calibration (top-1 cosine distance)

| index | on-topic hits: p10 / median / p90 | off-topic: min / median |
|---|---|---|
| e5 | 0.099 / 0.123 / 0.154 | 0.185 / 0.203 |
| gemini | 0.147 / 0.183 / 0.206 | 0.373 / 0.410 |

## Real queries from the log (14)

### VÖEN-in ləğvi proseduru necədir?

Shared top-5 sources: 0/5

**e5**
- `0.128` [9298] Salam. VÖEN-mi necə ləğv edə bilərəm?
- `0.132` [1516] VÖEN-in ləğv edilməsi.
- `0.132` [4651] 2004237452 nömrəli VÖEN-in ləğv olunması ücün uzun muddətdir ki, muraciət etmişəm. Ancaq hələ ləğv olunmayıb, xahiş olunur bu barədə köməklik edəsiniz.

**gemini**
- `0.161` [3641] VÖEN-i ləğv etmək üçün.
- `0.187` [1097] Salam. Mən vöeni ləğv elətdirmək istəyirəm. Lakin necə edəcəyimi bilmirəm. Zəhmət olmasa, yardımçı olardınız.
- `0.188` [1558] VÖEN-i onlayn ləğv etdirmək mümkündürmü? Mümkündürsə necə etmək lazımdır?

### Gəlir vergisi neçə faizdir?

Shared top-5 sources: 0/5

**e5**
- `0.135` [4629] Salam. Kriptovalyuta vergisi haqqında məlumat almaq istəyirdim. Neçə faiz vergi tutulur?
- `0.136` [6342] Salam. Bilmək istəyirdim ki, kirayə müqaviləsi bağlanan zaman mən neçə faiz vergi ödəməliyəm?
- `0.137` [4800] Salam! Mən çalışdığım xarici şirkətdən xüsusi endirimlə səhm almışam. İndi səhmləri satıb pulu nağdlaşdırmaq istəyirəm. Vergi ödənilməsi ilə bağlı maraqlanırdım

**gemini**
- `0.236` [3984] İşcinin aylıq gəliri 2536.74 manat təşkil edir və Vergi Məcəlləsinin 102.5-ci maddəsinə əsasən 50 manat güzəşti var. Həmin işçinin hesablanmalı gəlir vergisi nə
- `0.240` [6062] Salam. Mən SOCAR-ın "Neftqaztikinti" trestində çalışıram və aylıq əmək haqqım 1819 azn təşkil edir. Bilmək istərdim göstərilmiş məbləğin gəlir vergisinə cəlb ed
- `0.244` [881] Salam. Vergi tutulması minimum əmək haqqının neçə faizidir? Adi vətəndaşlar üçün Vergi güzəştləri kimlərə şamil olunur. Ailədə (onkoloji) xəstə olan insan olmas

### ƏDV qeydiyyatı üçün dövriyyə həddi nə qədərdir?

Shared top-5 sources: 4/5

**e5**
- `0.108` [10792] Məcburi ƏDV qeydiyyatı üçün tələb olunan dövriyyə həddi barədə məlumat verməyinizi xahiş edirəm.
- `0.133` [6896] Salam. Bilmək istərdim ki, mənfəət vergisi ödəyicisi olan ictimai iaşə müəssisəsi son 12 ayda 195 000 manat dəyərində xidmət göstərərək elektron qaimə yazmışdır
- `0.133` [10232] Salam.
Bizim müəssisə kənd təsərrüfatı məhsullarının (meyvə, tərəvəz) topdan satışı ilə məşğul olur. Bu məhsulları, Vergi Məcəlləsinin tələblərinə əsasən rəsmi

**gemini**
- `0.173` [10792] Məcburi ƏDV qeydiyyatı üçün tələb olunan dövriyyə həddi barədə məlumat verməyinizi xahiş edirəm.
- `0.205` [4324] Vergi ödəyicisi sadələşdirilmiş vergi ödəyicisidir. Əgər vergi ödəyicisi hesabat ilinin ortasında 200.000 artıq dövriyyəsi olduqda ədv ödəyicisi keçməlidir, yox
- `0.221` [10232] Salam.
Bizim müəssisə kənd təsərrüfatı məhsullarının (meyvə, tərəvəz) topdan satışı ilə məşğul olur. Bu məhsulları, Vergi Məcəlləsinin tələblərinə əsasən rəsmi

### Kriptovalyuta vergisi necə hesablanır?

Shared top-5 sources: 5/5

**e5**
- `0.094` [4629] Salam. Kriptovalyuta vergisi haqqında məlumat almaq istəyirdim. Neçə faiz vergi tutulur?
- `0.106` [9403] Kriptovalyuta əməliyyatlarından əldə olunan gəlir  hansı gəlir növünə aiddir ?
- `0.121` [4257] Kriptovalyuta mayning etmək və ondan pul qazanmaq qanuna ziddirmi, qadağandırmı?

**gemini**
- `0.220` [4629] Salam. Kriptovalyuta vergisi haqqında məlumat almaq istəyirdim. Neçə faiz vergi tutulur?
- `0.235` [9403] Kriptovalyuta əməliyyatlarından əldə olunan gəlir  hansı gəlir növünə aiddir ?
- `0.259` [4257] Kriptovalyuta mayning etmək və ondan pul qazanmaq qanuna ziddirmi, qadağandırmı?

### Bu sual heç bir mənbədə yoxdur — test üçün

Shared top-5 sources: 1/5

**e5**
- `0.138` [308] Salam. 2019-cu il 26 oktyabr tarixində Vergilər Nazirliyinə olacaq imtahan bağlı  ədəbiyyat siyahısını sayt yeniləndiyi üçün tapa bilmirəm, zəhmət olmasa bununl
- `0.143` [3024] Salam. Mən sual yazmışdım amma, bugünədək cavablandırılmayıb. Xahiş edirəm cavablandırardınız.
- `0.145` [5232] Mən magistram və disertasiya mövzum "Vergi uçotunun auditidir". Mən çox xahiş edirəm, bu barədə statistik məlumatları tapmaqda mənə kömək edəsiniz.

**gemini**
- `0.287` [417] Salam. Mən bilmək istərdim ki, vergi imtahanına hazırlaşan zaman düşən suallar, yalnız burdakı ədəbıyyat sıyahısında olanlar düşür?
- `0.298` [308] Salam. 2019-cu il 26 oktyabr tarixində Vergilər Nazirliyinə olacaq imtahan bağlı  ədəbiyyat siyahısını sayt yeniləndiyi üçün tapa bilmirəm, zəhmət olmasa bununl
- `0.312` [371] Keçid balı ne qədərdir?

### Növbəti vergi imtahanı nə zaman olacaq ?

Shared top-5 sources: 1/5

**e5**
- `0.118` [3973] Salam. Vergilər Nazirliyinə işə qəbul üzrə imtahan sonuncu dəfə 2019 il oktyabr ayında olub. Növbəti imtahana qeydiyat ne vaxt başlanacaq? İmtahan ne vaxt olaca
- `0.118` [4775] Salam. Vergilər nazirliyinə işə qəbul üçün növbəti imtahan nə zaman olacaq?
- `0.133` [6711] Salam. İqtisadiyyat Nazirliyi yanında Dövlət Vergi Xidmətinə növbəti işə qəbul imtahanı tarixi və şərtləri barədə məlumat bildirməyinizi xahiş edirəm.
Öncədən

**gemini**
- `0.191` [1041] Salam, bilmək olarmı imtahanın vaxtı nə vaxtdır?
- `0.199` [3973] Salam. Vergilər Nazirliyinə işə qəbul üzrə imtahan sonuncu dəfə 2019 il oktyabr ayında olub. Növbəti imtahana qeydiyat ne vaxt başlanacaq? İmtahan ne vaxt olaca
- `0.206` [978] Salam. Vergi orqanlarına işə qəbulla bağlı və imtahan tarixləri, neçə müddətdən bir imtahanların keçirilməsi barədə məlumat verə bilərsiniz? 
Öncədən təşəkkürl

### Xaricə çıxmaq ilə bağlı qadağanı hardan yoxlamaq olar ?

Shared top-5 sources: 3/5

**e5**
- `0.164` [7700] Salam. Mən bilmək istəyirəm ki, mən ölkədən başqa ölkəyə müvəqqəti getmək üçün çıxışıma icazə var ya yoxdur?
- `0.176` [9049] Salam, ölkədən çıxışıma məhdudiyyət varmı?
- `0.177` [8436] Salam. Mənim DSMF borcum vardı. Haqqımda məhkəmə qətnaməsi var. Bu gün tamamını ödədim. Bilmək istərdim ki, üzərimdən məhdudiyyət nə vaxt qalxacaq?

**gemini**
- `0.185` [6359] Salam. Mən bilmək istərdm ki, mənim adımda ölkədən çıxışa qadağa var ya yox? Xahiş edirəm, dəqiq məlumat verərdiniz.
- `0.194` [7700] Salam. Mən bilmək istəyirəm ki, mən ölkədən başqa ölkəyə müvəqqəti getmək üçün çıxışıma icazə var ya yoxdur?
- `0.240` [9049] Salam, ölkədən çıxışıma məhdudiyyət varmı?

### İşimi taksidən kuryerə dayişsəm proses necə olacaq ?

Shared top-5 sources: 0/5

**e5**
- `0.155` [631] Salam. Mən də hüquqi şəxs vöen açmışam. İndi Taksi işləmək istəyirəm. Vergi  necə olacaq?
- `0.177` [1150] Salam, mən şəxsi  maşınımla taksi kimi fəaliyyət göstərmək istəyirəm. Mənə necə kömək edə bilərsiz?
- `0.178` [1662] Yük maşınımla rayonlardan meyvə tərəvəz qətirirəm. Küçə arası səyyar satışı üçün, necə verqiödəməliyəm? Və nə qədər? Hansı sənədlər lazımdır?

**gemini**
- `0.293` [2365] Salam. Sizə dünən şirkət işçilərinin icazəsi barədə sorğu göndərmişdim. Bir neçə nömrə verdiniz əlaqə saxlamaq üçün amma heç biri cavab vermir! 
Kuryer fəaliyy
- `0.296` [5477] Salam, mən "Wolt"-da kuriyer kimi işə başlamaq istəyirəm, bunun üçün VÖEN lazımdır. Bugün ASAN xidmətə getdim, amma ala bilmədim. Çünki  qeydiyyatım rayondur, m
- `0.316` [3534] Sərt karantin rejimi ilə əlaqədar onlayn satış, malların çatdırılmasını həyata keçirmək istəyirəm. Mağazanı açmadan internet və ya telefonla sifariş qəbul edilə

### 168.1.5 maddəsi ilə bağlı məlumatın varmı

Shared top-5 sources: 1/5

**e5**
- `0.177` [6446] Mənə məktub gəlmişdir ki, mən 66150 manat dəyərində mal və ya xidmət etmişəm. Mənim bu işlərdən hec bir xəbərim yoxdur.
- `0.179` [450] Azərbaycan Respublikasının Vergilər Məcəlləsinin 164-cü maddəsinin 164.1 və 164.1.7 ci bəndləri hələ qüvvədədirmi?
- `0.180` [3615] Salam, bilmək istəyirdim fiksal nömrəni yığıram bazada tapılmır. Artıq 10 gündür. Bu halda nə etməliyəm?

**gemini**
- `0.244` [4884] Salam. VM-nin 168.1.5-ci maddəsinin 2-ci abzasında ("məsləhət, hüquq, mühasibat, mühəndis və ya reklam xidmətlərinin, həmçinin məlumatların işlənilməsi üzrə xid
- `0.276` [255] Salam Vergi Məcəlləsi 169.1-ci maddədə yazılır ki qeyri rezident 169.2-ci və ya 169.5-ci maddələrində adı çəkilən "vergi agenti" üçün xidmət göstərirsə yazır so
- `0.292` [5927] Salam. ƏDV-dən azad olunan malların siyası barədə tam məlumat almaq istəyirdim.

### rezident və qeyri rezident bu maddəyə aiddirmi

Shared top-5 sources: 0/5

**e5**
- `0.169` [255] Salam Vergi Məcəlləsi 169.1-ci maddədə yazılır ki qeyri rezident 169.2-ci və ya 169.5-ci maddələrində adı çəkilən "vergi agenti" üçün xidmət göstərirsə yazır so
- `0.171` [4920] Sənədsiz yerlərə vergi düşür ya yox?
- `0.173` [921] Salam. Rezident A şirkəti Qeyri rezident B şirkəti ilə xarici ölkədə C şirkətini təsis edirlər. A şirkəti C şirkətinə Nizamnamə kapitalına Əsas vəsaitini qoymaq

**gemini**
- `0.209` [8254] Salam. Sizdən aşağıda göstərdiyim məsələyə aydınlıq gətirməyinizi xahiş edirəm: Mənim övladım Azərbaycan vətəndaşıdır və Bakı şəhərində qeydiyyatdadır. Lakin, ö
- `0.210` [5033] Salam, AR-da daimi yaşayış icazəsi alan əcnəbi vətəndaş rezident sayılırmı?
- `0.237` [1232] Salam, hər vaxtınız xeyir, mən qeyri rezidentlərin ödəmə mənbəyindən vergi tutulması barədə izahlı 
nümunələri istəyirem bəndlər üzrə Vergi Məcəlləsində biraz

### salam

Shared top-5 sources: 0/5

**e5**
- `0.189` [3024] Salam. Mən sual yazmışdım amma, bugünədək cavablandırılmayıb. Xahiş edirəm cavablandırardınız.
- `0.201` [6729] VÖEN 1700672182!
Mənim adıma heç bir VÖEN yoxdur, mənə mesaj göndərirsiniz.
- `0.204` [1142] Salam vöeni necə baglatdıra bilərik?  Hara müraciət etmək lazımdır? Bunun üçün. Zəhmət olmasa, cavablandira bilərsiz?

**gemini**
- `0.375` [1340] Salam mənə yardım düşür?
- `0.383` [10306] Salam mənim adıma aktiv VÖEN var ?
- `0.384` [3890] Salam. 10.12.2020 ci il tarixində Saloğlu Mebel salonundan dəyəri 9049manat olan mebel almışam. 10.12.2020 ci il tarixdə əldə olunan çekin ƏDV portalında qeydiy

### vergide hansisa vakansiyalar olur?

Shared top-5 sources: 1/5

**e5**
- `0.156` [9382] Salam, Dövlət Vergi Xidmətinə işə qəbulla bağlı vakansiya elan olunub və ya elan olunacaqsa, hansı tarixdə gözlənilir. Zəhmət olmasa məlumat verərdiniz.
- `0.158` [2678] Salam. Bilmək istəyirdim ki, hal hazırda Vergilər Nazirliyində aktiv vakansiya movcuddur? Ya işə qəbul  prosesi gedir? Bir də ali təhsil kimi nəqliyyat fakültəs
- `0.159` [5088] Vergi xidmətinə işə qəbul üçün növbəti müsabiqənin keçirilməsi nə zaman gözlənilir?

**gemini**
- `0.220` [3785] Mövcud vakansiyalar barəsində məlumatı haradan ala bilərəm?
- `0.220` [791] Salam men Vergiler Nazirliyine imtahan vermey isteyirem,bilmek isteyirem ki menim ixtisasim buna imkan verir ya yox ,,bitirdiyim universitet ""Iqtisad -istehlak
- `0.222` [883] Salam, mən özüm ali təhsilliyəm, bilmək istəyirəm vergi orqanlarında işə girmək  üçün nə etmək lazımdır? İmtahanı vergi orqanı götürür, yoxsa dövlət qulluğu?

### sen hansi model ile ishleyirsen?

Shared top-5 sources: 0/5

**e5**
- `0.185` [1292] Mən Xüsusi notarius kimi fəaliyyət göstərirəm və muzdla işləyən işçilərim var. DSMF-na hər rüb İşəgötürən (0112) və Notarius (0310) kimi ayrı-ayrılıqda hesabat
- `0.185` [466] Salam. Mən 2 faizli sadələşdirilmiş vergi ödəyicisiyəm. Fiziki şəxs olaraq fəaliyyət göstərirəm. Göstərdiyimiz fəaliyyət psixofizioloji reabilitasiya mərkəzidir
- `0.187` [138] Salam.MƏCBURİ DÖVLƏT SOSİAL SIĞORTASI ÜZRƏ HESABAT-da Kənd İcra Nüməyəndəliklərinin M.D.S.S. məqsədləri üçün fəaliyyət növünün kodu hansı olmalıdır?
0112 yoxsa

**gemini**
- `0.326` [1755] Salam, mən 2 ay bundan əvvəl Stanley Beverages -Baku müəssisəsindən işdən çıxmışam. Dünyada baş vermiş Covid-19-la əlaqədar rayondan Bakıya gələ   bilmirəm ki,
- `0.326` [4122] Salam, mən fərdi sahibkaram, gözəllik salonu işlədirəm, salonda kassa apparatı mövcuddur. Bir neçə işçim var, onları əmək müqavilə əsasında işlədirəm. Bir neçə
- `0.333` [1751] Salam, mən market daxilində uşaq klubunda çalışıram (əmək müqaviləmdə təlimatçı qeyd olunub). Biz martın 5-dən pandemiya səbəbilə işləmirik və əmək haqqı satıcı

### Fiziki şəxslərin gəlir vergisi neçə faizdir?

Shared top-5 sources: 1/5

**e5**
- `0.112` [5015] Salam, zəhmət olmazsa cavablandırardınız ki, 2000-ci-2004-cü illər ərzində fərdi sahibkarın gəlir vergisi dərəcəsi nə qədər olmuşdur?
- `0.126` [919] Salam. Mənim sualım belədir. Fiziki şəxsin gəlir vergisi bəyannaməsi tərtib edilərkən xərclərə bankdan nağdlaşdırma zamanı tutulan 1% (bir faiz) vergi xərci dax
- `0.127` [681] Salam. Sualım İcarə Müqaviləsi ilə bağlıdır. Sual: Mən Hüquqi şəxs kimi öhdəliyimdə olan obyekti Fiziki şəxsə İcarəyə vermişəm bilmək istəyirəm İcarə verdiyim o

**gemini**
- `0.221` [5015] Salam, zəhmət olmazsa cavablandırardınız ki, 2000-ci-2004-cü illər ərzində fərdi sahibkarın gəlir vergisi dərəcəsi nə qədər olmuşdur?
- `0.225` [881] Salam. Vergi tutulması minimum əmək haqqının neçə faizidir? Adi vətəndaşlar üçün Vergi güzəştləri kimlərə şamil olunur. Ailədə (onkoloji) xəstə olan insan olmas
- `0.226` [1237] Mənim fiziki şəxsəm. İcazəm yoxdur, asan imza nomrəm var. sertifikasiyam yoxdur. İşləmirəmsə vergi verməliyəm? Azərbaycan Respublikası Vergilər Nazirliyinin 30
