import json, re, unicodedata, collections, itertools, html
from urllib.parse import unquote
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data' / 'raw'
piv = json.load(open(RAW/'pivene_all.json'))
cw = json.load(open(RAW/'cw_all.json'))
cs = json.load(open(RAW/'cs_all.json'))
cs_types = json.load(open(RAW/'cs_types.json'))
_gv = RAW/'gv_all.json'; gv = json.load(open(_gv)) if _gv.exists() else []
_vn = RAW/'vinum_all.json'; vn = json.load(open(_vn)) if _vn.exists() else []
_wc = RAW/'wc_all.json'; wc = json.load(open(_wc)) if _wc.exists() else []
_vi = RAW/'vinum_uk_images.json'; vn_imgs = json.load(open(_vi)) if _vi.exists() else []
VN_CDN = 'https://vinumfinewinescom-21644.kxcdn.com/wp-content/uploads/'
_VSTOP = set('ch chateau domaine dom the de du des la le les di da del della st saint ex mag btl cru premier 1er grand gc 1c and et owc oc bot hlf mags halves reconditioned stained label ready stock case of x cl pere fils poderi famille vigneron'.split())
_VLEAD = set('ch chateau domaine dom poderi famille les le la the clos'.split())
def _vnorm(n):
    n = n.lower().replace('&#8217;', "'"); n = re.sub(r'\(.*?\)|\[.*?\]', ' ', n); n = re.sub(r'\b(19|20)\d\d\b', ' ', n)
    n = re.sub(r'\b\d+x\d+cl\b', ' ', n); n = re.sub(r'\b\d+(bot|mag|hlf)\b', ' ', n)
    return re.sub(r'[^a-z0-9 ]', ' ', n).split()
def _vtoks(w): return {t for t in w if t not in _VSTOP and len(t) > 1}
def _vlead(w): return next((t for t in w if t not in _VLEAD and len(t) > 1), '')
_vn_index = [(_vtoks(w), _vlead(w), i) for n, i in vn_imgs for w in [_vnorm(n)]]
def vinum_image(wine):
    w = _vnorm(wine); t = _vtoks(w); ld = _vlead(w)
    if not t: return ''
    cands = sorted((len(ut), i) for ut, ul, i in _vn_index if t <= ut and ul == ld)
    return VN_CDN + cands[0][1] if cands else ''
_det = ROOT / 'data' / 'cs_details.json'
cs_details = json.load(open(_det)) if _det.exists() else {}

# ---------- helpers ----------
def strip_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))

def clean(s):
    s = strip_accents(html.unescape(s or '')).replace('’', "'")
    return re.sub(r'\s+', ' ', s).strip()

VINT_RE = re.compile(r'\b(19[0-9]{2}|20[0-4][0-9])\b')
def vintage_of(name):
    yrs = VINT_RE.findall(name)
    if 'NV' in name.upper().split() or re.search(r'\bN\.?V\.?\b', name, re.I):
        return 'NV'
    if yrs:
        # vertical sets etc: take last year
        return yrs[-1]
    return 'NV' if re.search(r'champagne|brut|solera|non vintage', name, re.I) else ''

def size_of(name, default=750):
    n = name.lower()
    m = re.search(r'(\d+(?:\.\d+)?)\s*(ml|cl|l)\b', n)
    if m:
        v = float(m.group(1)); u = m.group(2)
        ml = v if u == 'ml' else v*10 if u == 'cl' else v*1000
        return int(round(ml))
    m = re.search(r'\b(magnum|jeroboam|double magnum|imperial|methuselah)\b', n)
    if m and m.group(1) == 'imperial' and re.search(r'moet|chandon', n): m = None   # Moet "Brut Imperial" is a cuvee, not a 6L
    if m:
        return {'magnum':1500,'double magnum':3000,'jeroboam':3000,'imperial':6000,'methuselah':6000}[m.group(1)]
    return default

def pack_of(name):
    n = name.lower()
    m = re.search(r'(?:of|x|case of|owc|occ|bundle of)\s*(\d+)\s*(?:bottles?|bot|btls?)\b', n) or \
        re.search(r'\b(\d+)\s*(?:x|bottles?|bot|btls?)\b', n) or \
        re.search(r'(?:owc|occ)\s*(\d+)', n)
    if m:
        k = int(m.group(1))
        if 2 <= k <= 24: return k
    if re.search(r'mixed case|vertical set|collection case|assortment', n):
        return 0  # bundle of unknown composition
    return 1

SECOND = {'petit','petite','carmes','pavillon','forts','reserve','dame','griffons','segla','tourelles',
          'croix','clos','marquis','alter','ego','chapelle','amiral','aromes','sirene','connetable',
          'dauphin','hauts','pagodes','esprit','blason','fiefs','lady','langoa','moulin','baron','comtesse',
          'blanc','rouge','rose','rosato','bianco','rosso','magnum','gbx','ngbx','owc','occ','box','gift',
          'p2','p3','luminous','grand','cru','1er','premier','riserva','reserva','gran','vecchie','vieilles','vignes'}
STOP = {'chateau','ch','domaine','dom','the','de','du','des','la','le','les','di','da','del','della','et','and',
        'wine','wines','vintage','ml','l','cl','bottle','bottles','bot','ex','ex-chateau','ex-domaine','with','w','o',
        'cuvee','maison','tenuta','fattoria','az','azienda','agricola','winery','estate','cantina','weingut','bodegas','bodega',
        'nv','in','of','a','an','en','sur','aoc','aop','doc','docg','igt','igp','vdp','new','classic','classico'}

def tokens(name):
    n = clean(name).lower()
    n = re.sub(r'\(.*?\)', ' ', n)
    n = VINT_RE.sub(' ', n)
    n = re.sub(r'\d+(?:\.\d+)?\s*(?:ml|cl|l)\b', ' ', n)
    n = re.sub(r'[^a-z0-9 ]', ' ', n)
    n = re.sub(r'\bgrands?\s+echezeaux\b', 'grandsechezeaux', n)
    # Latour a Pomerol (Pomerol) is a different estate from Ch Latour (Pauillac): keep it as one token
    n = re.sub(r'\blatour\s*a\s*pomerol\b', 'latourapomerol', n)
    toks = [t for t in n.split() if t not in STOP]
    return set(toks)

TYPE_ORDER = ['Red','White','Sparkling','Rose','Dessert','Fortified','Spirits','Sake','Non-Alcoholic','Accessories','Other']

def infer_type(name, hint=''):
    n = clean(name).lower()
    if hint: return hint
    if re.search(r'\b(champagne|brut|prosecco|cava|spumante|franciacorta|cremant|sekt|sparkling|blanc de blancs|blanc de noirs|dosage zero)\b', n): return 'Sparkling'
    if re.search(r'\b(port|porto|tawny|ruby|sherry|jerez|madeira|marsala|pedro ximenez|px|fino|oloroso|amontillado|banyuls|vermouth)\b', n): return 'Fortified'
    if re.search(r'\b(rose|rosato|rosado)\b', n): return 'Rose'
    if re.search(r"\b(sauternes|yquem|rieussec|moscato|vin santo|tokaji|tokay|sgn|vendange tardive|vendages? tardives?|recioto|passito|icewine|eiswein|trockenbeerenauslese|beerenauslese|auslese|late harvest|sweet|doux|dessert|guiraud|climens|suduiraut|coutet|doisy)\b", n): return 'Dessert'
    if re.search(r'\b(whisky|whiskey|bourbon|cognac|armagnac|brandy|gin|vodka|rum|tequila|mezcal|grappa|calvados|liqueur|liquor|aperitif|absinthe|sake|shochu|umeshu|eau de vie)\b', n): return 'Spirits'
    if re.search(r'\b(cheval blanc)\b', n) and not re.search(r'petit', n): return 'Red'
    if re.search(r'\b(blanc|bianco|blanco|chardonnay|riesling|sauvignon|chablis|meursault|montrachet|charlemagne|pouilly|sancerre|soave|gruner|gewurz\w*|pinot gris|pinot grigio|albarino|verdejo|semillon|viognier|vermentino|gavi|lugana|pecorino|trebbiano|muscadet|vouvray|condrieu|chenin|muscat|white|weiss|greco|fiano|falanghina|arneis|cortese|torrontes|godello|verdicchio|friulano|hermitage blanc|marsanne|roussanne|aligote|bouzeron|saint aubin|st aubin|chassagne|puligny|macon|rully|montagny|pessac leognan blanc|haut brion blanc|smith haut lafitte blanc|carbonnieux blanc|laville)\b', n): return 'White'
    return 'Red'

COUNTRY_FIX = {'usa':'USA','us':'USA','united states':'USA','uk':'United Kingdom','france':'France','italy':'Italy','spain':'Spain','germany':'Germany','australia':'Australia','new zealand':'New Zealand','new-zealand':'New Zealand','chile':'Chile','argentina':'Argentina','japan':'Japan','portugal':'Portugal','austria':'Austria','south africa':'South Africa','china':'China','others':'','other':'','':''}
def norm_country(c):
    c = clean(c).lower()
    return COUNTRY_FIX.get(c, c.title())

REGION_KW = [
 (r'\b(pauillac|margaux|saint julien|st julien|saint estephe|st estephe|pomerol|saint emilion|st emilion|pessac|leognan|graves|medoc|sauternes|barsac|bordeaux|haut brion|lafite|latour|mouton|cheval blanc|petrus|ausone|angelus|pavie|montrose|cos d estournel|palmer|lynch bages|pichon|leoville|ducru|beychevelle|calon segur|figeac|canon|troplong|valandraud|lafleur|le pin|vieux chateau certan|trotanoy|fronsac|castillon|moulis|listrac|lalande)\b','Bordeaux'),
 (r'\b(burgundy|bourgogne|chablis|meursault|montrachet|charlemagne|corton|pommard|volnay|beaune|nuits|vosne|romanee|chambolle|musigny|gevrey|chambertin|morey|clos de la roche|clos saint denis|echezeaux|vougeot|richebourg|santenay|chassagne|puligny|saint aubin|st aubin|macon|pouilly fuisse|rully|mercurey|givry|montagny|marsannay|fixin|aloxe|pernand|savigny|ladoix|auxey|monthelie|saint romain|bouzeron|cote de nuits|cote de beaune|hospices de beaune|drc|leroy|rousseau|roumier|dujac|lignier|groffier|fourrier|mugnier|liger belair|coche dury|lafon|roulot|ramonet|leflaive|sauzet|bonneau du martray|bichot|drouhin|jadot|faiveley|bouchard|louis latour|chanson|champy)\b','Burgundy'),
 (r'\b(champagne|krug|dom perignon|cristal|roederer|salon|bollinger|billecart|ruinart|moet|veuve clicquot|perrier jouet|pol roger|taittinger|laurent perrier|henri giraud|jacquesson|egly|selosse|lanson|deutz|philipponnat|gosset|ployez|palmer & co|duval leroy|de venoge|ayala|charles heidsieck|piper|drappier|agrapart|larmandier)\b','Champagne'),
 (r'\b(rhone|chateauneuf|hermitage|cote rotie|cornas|saint joseph|st joseph|crozes|gigondas|vacqueyras|condrieu|rasteau|cairanne|guigal|chapoutier|jaboulet|chave|rayas|beaucastel|pegau|usseglio|janasse|vieux telegraphe|clos des papes|bosquets|tardieu|lirac|tavel|ventoux|luberon|sainte croix)\b','Rhone'),
 (r'\b(loire|sancerre|pouilly fume|vouvray|chinon|muscadet|saumur|bourgueil|anjou|savennieres|menetou|quincy|dagueneau|huet|clos rougeard)\b','Loire'),
 (r'\b(alsace|hugel|trimbach|zind|humbrecht|weinbach|lorentz|gewurz\w*)\b','Alsace'),
 (r'\b(beaujolais|fleurie|morgon|moulin a vent|brouilly|chenas|julienas|roilette|rottiers|foillard|lapierre|thevenet)\b','Beaujolais'),
 (r'\b(provence|bandol|tempier|ott|whispering angel|minuty|miraval)\b','Provence'),
 (r'\b(languedoc|roussillon|corbieres|minervois|pic saint loup|banyuls|maury|grange des peres|mas de daumas)\b','Languedoc'),
 (r'\b(jura|arbois|chateau chalon|savoie|overnoy|ganevat|tissot)\b','Jura'),
 (r'\b(cognac|armagnac|calvados)\b','Cognac & Armagnac'),
 (r'\b(tuscany|toscana|chianti|brunello|montalcino|bolgheri|sassicaia|ornellaia|tignanello|solaia|masseto|montepulciano d abruzzo|vino nobile|maremma|antinori|frescobaldi|biondi santi|soldera|fontodi|felsina|isole e olena|poggio|castello|tenuta|rosso di|le pergole|flaccianello|guado al tasso|le macchiole|tua rita|redigaffi|argiano|siro pacenti|canalicchio|la rasina|monsanto|trebbio)\b','Tuscany'),
 (r'\b(piedmont|piemonte|barolo|barbaresco|langhe|nebbiolo|barbera|dolcetto|roero|gaja|conterno|giacosa|sandrone|altare|scavino|vietti|mascarello|rinaldi|cappellano|roagna|bersano|boroli|paitin|monfortino|moscato d asti|gavi|arneis)\b','Piedmont'),
 (r'\b(veneto|amarone|valpolicella|ripasso|soave|prosecco|lugana|dal forno|quintarelli|allegrini|tommasi|zenato|brigaldara|masi|bertani|tedeschi|astoria)\b','Veneto'),
 (r'\b(sicily|sicilia|etna|nero d avola|marsala|planeta|donnafugata|tasca|passopisciaro)\b','Sicily'),
 (r'\b(sardinia|sardegna|argiolas|cannonau|vermentino di sardegna)\b','Sardinia'),
 (r'\b(abruzzo|marche|umbria|puglia|primitivo|salento|campania|taurasi|friuli|alto adige|trentino|lombardy|franciacorta|velenosi|varvaglione|lungarotti|offida|pecorino|verdicchio|montepulciano)\b','Other Italy'),
 (r'\b(rioja|ribera del duero|ribera|priorat|priorato|vega sicilia|pingus|unico|valbuena|alion|artadi|muga|la rioja alta|lopez de heredia|cvne|contador|roda|aalto|pesquera|clos erasmus|l ermita|palacios|mas doix|toro|bierzo|rueda|rias baixas|albarino|jumilla|cava|jerez|manzanos|siglo|solano|gregorio martinez|penedes|montsant|navarra)\b','Spain'),
 (r'\b(mosel|rheingau|rheinhessen|pfalz|nahe|baden|franken|riesling|egon muller|jj prum|prum|keller|donnhoff|fritz haag|schloss|seehof|loosen|selbach|kesselstatt|haart|molitor|markus)\b','Germany'),
 (r'\b(napa|sonoma|oregon|washington|california|opus one|screaming eagle|harlan|dominus|napanook|caymus|silver oak|ridge|kistler|kongsgaard|shafer|joseph phelps|insignia|stags leap|duckhorn|cakebread|far niente|heitz|colgin|bond|scarecrow|sine qua non|aubert|peter michael|hundred acre|bryant|dalla valle|continuum|promontory|quilceda|leonetti|walla walla|willamette|russian river|paso robles|santa barbara|rhys|dumol|littorai)\b','USA'),
 (r'\b(barossa|mclaren|coonawarra|margaret river|hunter|yarra|eden valley|clare|adelaide|tasmania|victoria|heathcote|penfolds|grange|henschke|hill of grace|torbreck|elderton|wynns|leeuwin|cullen|vasse felix|moss wood|yalumba|jim barry|d arenberg|two hands|mollydooker|kaesler|greenock|rockford|clarendon|giaconda|bass phillip|wendouree|noon|glaetzer|kilikanoon|john duval|standish|hentley|langmeil|seppeltsfield|cape mentelle|xanadu|voyager|howard park|tyrrell|brokenwood|mount mary|yarra yering|bindi)\b','Australia'),
 (r'\b(marlborough|central otago|hawkes bay|hawke s bay|martinborough|waiheke|cloudy bay|felton road|ata rangi|craggy range|te mata|saint clair|dog point|greywacke|kumeu|misha|lawson|rippon|burn cottage|two paddocks|pegasus bay|neudorf|fromm|villa maria|oyster bay)\b','New Zealand'),
 (r'\b(maipo|colchagua|casablanca|aconcagua|almaviva|don melchor|sena|clos apalta|casa silva|concha y toro|errazuriz|montes|lapostolle|vik|cono sur|undurraga|santa rita|carmenere)\b','Chile'),
 (r'\b(mendoza|argentina|malbec|catena|cheval des andes|zuccardi|trivento|kaiken|achaval|bodega norton|trapiche|luigi bosca|el enemigo|colome|bressia)\b','Argentina'),
 (r'\b(douro|porto|dao|alentejo|madeira|vinho verde|quinta|niepoort|taylor|graham|fonseca|dow|warre|cockburn|croft|sandeman|ramos pinto)\b','Portugal'),
 (r'\b(stellenbosch|swartland|western cape|south africa|kanonkop|meerlust|sadie|mullineux|hamilton russell|boekenhoutskloof|rust en vrede|vergelegen|thelema|vilafonte|klein constantia|alheit)\b','South Africa'),
 (r'\b(wachau|kamptal|kremstal|burgenland|gruner|austria|hirtzberger|knoll|prager|alzinger|pichler|brundlmayer|hirsch|nikolaihof|kracher|velich|moric)\b','Austria'),
 (r'\b(scotland|scotch|speyside|islay|highland|lowland|campbeltown|macallan|glenfiddich|glenlivet|lagavulin|laphroaig|ardbeg|bowmore|bruichladdich|port charlotte|octomore|talisker|highland park|dalmore|glenmorangie|balvenie|aberlour|glendronach|benriach|glenfarclas|springbank|kilkerran|bunnahabhain|caol ila|bruichladdich|glen scotia|clynelish|oban|mortlach|craigellachie|aultmore|tamdhu|glen grant|glenrothes|glengoyne|arran|jura|tomatin|ben nevis|benromach|johnnie walker|chivas|ballantine|dewar|famous grouse|monkey shoulder|compass box|douglas laing|gordon macphail|cadenhead|signatory|hunter laing)\b','Scotland'),
 (r'\b(japan|japanese|yamazaki|hakushu|hibiki|nikka|yoichi|miyagikyo|taketsuru|chichibu|ichiro|mars|kaiyo|akashi|togouchi|suntory|kirin|fuji|sake|junmai|daiginjo|ginjo|nigori|dassai|kubota|hakkaisan|juyondai|aramasa|kokuryu|tatenokawa|isojiman|kamoshibito|born|denshin|sake hundred|byakko|mizubasho|nanbu bijin|zaku|jikon|hiroki|kid|tedorigawa|kikuhime|masumi|kamotsuru|urakasumi|kirinzan|hakutsuru|gekkeikan|ozeki|umeshu|choya|shochu|iichiko)\b','Japan'),
]
def infer_region(name, country=''):
    n = clean(name).lower().replace("'", ' ')
    n = re.sub(r'[^a-z0-9 ]', ' ', n)
    for pat, reg in REGION_KW:
        if re.search(pat, n): return reg
    return ''

REGION_COUNTRY = {'Bordeaux':'France','Burgundy':'France','Champagne':'France','Rhone':'France','Loire':'France','Alsace':'France','Beaujolais':'France','Provence':'France','Languedoc':'France','Jura':'France','Cognac & Armagnac':'France','Tuscany':'Italy','Piedmont':'Italy','Veneto':'Italy','Sicily':'Italy','Sardinia':'Italy','Other Italy':'Italy','Spain':'Spain','Germany':'Germany','USA':'USA','Australia':'Australia','New Zealand':'New Zealand','Chile':'Chile','Argentina':'Argentina','Portugal':'Portugal','South Africa':'South Africa','Austria':'Austria','Scotland':'Scotland','Japan':'Japan'}

def title_case(s):
    small = {'de','du','des','la','le','les','di','da','del','della','et','and','of','the','en','y','a','sur','von','der','zu'}
    out = []
    for i, w in enumerate(s.split()):
        lw = w.lower()
        if not re.sub(r"['’.-]", '', lw).isalpha():
            out.append(w.upper() if re.match(r'^(nv|igt|doc|docg|aoc|owc|occ|gbx|ngbx|sgn|px|xo|vs|vsop)$', lw) else w)
        elif not lw.isalpha():
            w2 = re.sub(r"(^|['\u2019-])([a-z])", lambda m: m.group(1) + m.group(2).upper(), lw)
            out.append(re.sub(r"'S$", "'s", w2))
        elif lw in small and i > 0:
            out.append(lw)
        elif re.match(r'^(nv|igt|doc|docg|aoc|owc|occ|gbx|ngbx|sgn|px|xo|vs|vsop|mo|jj)$', lw):
            out.append(lw.upper())
        else:
            out.append(lw[0].upper() + lw[1:])
    return ' '.join(out)

# ---------- normalise each source ----------
items = []

# Pivene: [title, handle, type, vendor, price, compare, vtitle, available, country, region, vintage, format, rating, img]
PIV_TYPE = {'Red Wine':'Red','White Wine':'White','white':'White','Sparkling':'Sparkling','Rose':'Rose','Dessert Wine':'Dessert','Fortified Wine':'Fortified','Spirits':'Spirits','Sake':'Sake','Accessories':'Accessories'}
for r in piv:
    title, handle, ptype, vendor, price, compare, vtitle, avail, country, region, vint, fmt, rating, img = r
    name = clean(title)
    t = PIV_TYPE.get(ptype, 'Other')
    pack = pack_of(name)
    m = re.search(r'bundle of (\d+)', (vtitle or '').lower())
    if m: pack = int(m.group(1))
    size = size_of(name, 720 if t == 'Sake' else 750)
    reg = clean(region).title() if region else ''
    reg = {'Rhone':'Rhone','Napa':'USA','Others':'','Tuscany':'Tuscany','Piedmont':'Piedmont','Veneto':'Veneto'}.get(reg, reg)
    if reg in ('Others', '') : reg = infer_region(name)
    if reg in ('Usa',): reg = 'USA'
    items.append(dict(src='pivene', name=name, type=t, country=norm_country(country), region=reg,
        vintage=(vint.upper() if vint else vintage_of(name)), size=size, pack=pack,
        price=float(price) if price else None, compare=float(compare) if compare else None,
        in_stock=bool(avail), stock=2 if avail else 0, url='https://www.pivene.com/products/'+handle, img=img or '',
        rating=rating or '', producer=clean(vendor)))

# Crystal Wines: [name,id,permalink,price,regular,sale,range,in_stock,ptype,cats,bottle,img,sd,country,colour,wtype,region,vintage]
for r in cw:
    name, pid, url, price, regular, sale, prange, stock, ptype, cats, bottle, img, sd, country, colour, wtype, region, vint = r
    if ptype == 'gift-card' or 'E-Gift Card' in cats: continue
    nm = title_case(clean(name))
    catl = cats.lower()
    if 'accessor' in catl: t = 'Accessories'
    elif 'non-alcoholic' in catl: t = 'Non-Alcoholic'
    elif any(k in catl for k in ('spirit','whisky','brandy','gin','rum','vodka','cognac','sake')): t = 'Spirits' if 'sake' not in catl else 'Sake'
    elif wtype == 'Sparkling': t = 'Sparkling'
    elif wtype == 'Sweet': t = 'Dessert'
    elif colour in ('Red','White','Rose'): t = colour
    else: t = infer_type(nm)
    if t == 'Spirits' and re.search(r'\b(port|sherry|madeira|px|pedro ximenez)\b', nm.lower()): t = 'Fortified'
    size = int(re.sub(r'\D','', bottle.split('|')[0])) if bottle and re.sub(r'\D','', bottle.split('|')[0]) else size_of(nm, 700 if t=='Spirits' else 750)
    pack = pack_of(nm)
    if any(k in catl for k in ('pristine cases','mixed cases','privee cases')) and pack == 1: pack = 0
    p = float(price)/100 if price else None
    reg = float(regular)/100 if regular else None
    cty = norm_country(country.split('|')[0]) if country else ''
    rg = clean(region.split('|')[0]) if region else ''
    rg = {'Rhone':'Rhone','Napa Valley':'USA','Napa':'USA'}.get(rg, rg)
    if not rg: rg = infer_region(nm)
    v = (vint.split('|')[0] if vint else '') or vintage_of(nm)
    items.append(dict(src='crystal', name=nm, type=t, country=cty, region=rg, vintage=v, size=size, pack=pack,
        price=p, compare=reg if reg and p and reg > p else None, in_stock=bool(stock), stock=2 if stock else 0, url=url, img=img or '',
        rating='', producer='', note=clean(sd)))

# Cornerstone: [cat, page, title, href, list_price, offer_price, off, stocktxt, buy/enquire, img]
cs_type_map = {}
for cat, title, href in cs_types:
    k = cat.split('/')[1]
    cs_type_map[href] = {'white':'White','sweet':'Dessert','champagne':'Sparkling'}[k]
CS_COUNTRY = {'france':'France','italy':'Italy','spain':'Spain','germany':'Germany','chile':'Chile','us':'USA','australia':'Australia','new-zealand':'New Zealand','spirits':''}
seen_cs = set()
for r in cs:
    cat, page, title, href, lp, op, off, stocktxt, mode, img = r
    if href in seen_cs: continue
    seen_cs.add(href)
    nm = clean(title)
    if cat == 'spirits':
        t = 'Spirits'
        if re.search(r'\b(port|porto|sherry|madeira|px|pedro ximenez|vermouth)\b', nm.lower()): t = 'Fortified'
        if re.search(r'\b(sake|junmai|daiginjo|umeshu)\b', nm.lower()): t = 'Sake'
        if re.search(r'\b(water|san martino|mineral)\b', nm.lower()): t = 'Non-Alcoholic'
    else:
        t = cs_type_map.get(href) or infer_type(nm)
        if href in cs_type_map and cs_type_map[href] == 'White' and re.search(r'\bcheval blanc\b', nm.lower()) and 'petit' not in nm.lower():
            t = 'Red'
    det = cs_details.get(href) or {}
    dt = (det.get('type') or '').strip().lower()
    if cat != 'spirits' and dt in ('red', 'white', 'rose', 'sparkling', 'champagne', 'dessert', 'sweet'):
        t = {'red':'Red','white':'White','rose':'Rose','sparkling':'Sparkling','champagne':'Sparkling','dessert':'Dessert','sweet':'Dessert'}[dt]
        if dt == 'white' and re.search(r'\bcheval blanc\b', nm.lower()) and 'petit' not in nm.lower(): t = 'Red'
    size = size_of(nm, 700 if t == 'Spirits' else 750)
    pack = pack_of(nm)
    if re.search(r'\(owc 1\)', nm.lower()): pack = 1
    price = op if op is not None else lp
    compare = lp if (op is not None and lp and lp > op) else None
    cty = CS_COUNTRY.get(cat, '') or norm_country(det.get('country') or '')
    reg = infer_region(nm) or clean(det.get('region') or '').title()
    if not cty and reg: cty = REGION_COUNTRY.get(reg, '')
    items.append(dict(src='cornerstone', name=nm, type=t, country=cty, region=reg, vintage=vintage_of(nm), size=size, pack=pack,
        price=price, compare=compare, in_stock=(mode == 'buy'), stock=2 if mode == 'buy' else 1, url='https://shop.cornerstonewines.com'+href, img=img or '',
        rating=clean(det.get('rating') or ''), producer=''))

# Grand Vin: [title, handle, product_type, vendor, tags, variant_title, price, compare, available, img]
GV_TYPE = {'Red Wine':'Red','White Wine':'White','Rose':'Rose','Champagne':'Sparkling','Sparkling':'Sparkling','Fortified Wine':'Fortified',
           'Spirits':'Spirits','Whiskey':'Spirits','Sake':'Sake','Accessories':'Accessories','Glassware':'Accessories','Gift':'Accessories'}
for r in gv:
    title, handle, ptype, vendor, tags, vt, price, compare, avail, img = r
    if ptype in ('Event', 'Olive Oil') or 'gift-voucher' in handle: continue
    t = GV_TYPE.get(ptype, 'Other')
    vt = clean(vt)
    m = re.match(r'^(\d{4}|NV)\b(.*)$', vt, re.I)
    vint = m.group(1).upper() if m else vintage_of(title)
    rest = (m.group(2) if m else vt)
    if rest.strip().lower() in ('', 'default title'): rest = ''
    nm = clean(title)
    if vint and vint != 'NV' and vint not in nm: nm = f'{nm} {vint}'
    # keep meaningful variant qualifiers (format, gift box), drop logistics notes
    rest = re.sub(r'\*?\s*(arriving|ships?|ready stock)[^)\]]*', '', rest, flags=re.I).strip(' ()*-')
    if rest and not re.match(r'^(default title|1 bottle)$', rest, re.I): nm = f'{nm} ({rest})'
    size = size_of(nm, 720 if t == 'Sake' else (700 if t == 'Spirits' else 750))
    pack = pack_of(nm)
    pk = re.search(r'bundle of (\d+)', vt.lower())
    if pk: pack = int(pk.group(1))
    p = float(price) if price else None
    cmp_ = float(compare) if compare else None
    tagl = [x.strip() for x in tags.split('|') if x.strip()]
    GV_REG = {'Burgundy':'Burgundy','Bordeaux':'Bordeaux','Rhone':'Rhone','Champagne':'Champagne','Loire':'Loire','Alsace':'Alsace','Napa Valley':'USA',
              'Piedmont':'Piedmont','Tuscany':'Tuscany','Veneto':'Veneto','Rioja':'Spain',"Hawke's Bay":'New Zealand','Marlborough':'New Zealand','Nahe':'Germany','Mosel':'Germany','Barossa':'Australia'}
    reg = infer_region(nm + ' ' + vendor) or next((GV_REG[x] for x in tagl if x in GV_REG), '') or next((GV_REG[x.title()] for x in tagl if x.title() in GV_REG), '')
    cty = REGION_COUNTRY.get(reg, '') or next((norm_country(x) for x in tagl if norm_country(x) in REGION_COUNTRY.values() or x in ('China','Austria','South Africa','Argentina','Portugal')), '')
    items.append(dict(src='grandvin', name=nm, type=t, country=cty, region=reg, vintage=vint or '', size=size, pack=pack,
        price=p, compare=cmp_ if cmp_ and p and cmp_ > p else None, in_stock=bool(avail), stock=2 if avail else 0,
        url='https://www.grandvin.com.sg/products/'+handle+'?variant='+re.sub(r'[^a-z0-9]+','-',vt.lower()).strip('-'), img=img or '', rating='', producer=clean(vendor)))

# Vinum Fine Wines SG: [category, vintage, wine, format, qty, unit_price]
VN_CAT = {'White Bordeaux':('White','Bordeaux'),'Red Bordeaux':('Red','Bordeaux'),'Red Burgundy & Beaujolais':('Red','Burgundy'),
          'White Burgundy':('White','Burgundy'),'Rhone':('Red','Rhone'),'Alsace':('White','Alsace'),'Champagne':('Sparkling','Champagne'),
          'Jura':('White','Jura'),'Languedoc-Rousillon':('Red','Languedoc'),'Loire':('White','Loire'),'Provence':('Rose','Provence'),
          'Sauternes':('Dessert','Bordeaux'),'Argentina':('Red','Argentina'),'Australia':('Red','Australia'),'Austria':('White','Austria'),
          'Chile':('Red','Chile'),'England':('Sparkling','England'),'Germany':('White','Germany'),'Italy':('Red','Other Italy'),
          'New Zealand':('Red','New Zealand'),'Portugal':('Fortified','Portugal'),'South Africa':('Red','South Africa'),'Spain':('Red','Spain'),
          'USA':('Red','USA'),'Whiskies & Spirits':('Spirits','')}
VN_FMT = {'Btl':(750,1),'Mag':(1500,1),'HLF':(375,1),'JERO':(3000,1),'Case of 6 Btls':(750,6),'Case of 3 Btls':(750,3),'Case of 12 Btls':(750,12),
          'Case of 4 Btls':(750,4),'Case of 3 Mags':(1500,3),'Case of 6 Mags':(1500,6),'Case of 12 Halves':(375,12),'CS4M':(1500,4),'CS24H':(375,24)}
for r in vn:
    cat, vint, wine, fmt, qty, price = r
    t, reg = VN_CAT.get(cat, ('Red', ''))
    nm = clean(wine)
    nm = re.sub(r'\s*\((\d+)(bot|mag|hlf)/O(W)?C\)', '', nm, flags=re.I)        # (6bot/OWC) -> handled via format
    nm = re.sub(r'\s*\((mag|dmg|jrb|imp|hlf)\)', '', nm, flags=re.I)
    nm = re.sub(r'\s*\[(ex-chateau|ex-domaine|reconditioned[^\]]*)\]', lambda m: f' ({m.group(1).title()})', nm, flags=re.I)
    low = nm.lower()
    if t == 'Red' and re.search(r'\b(blanc|bianco|white|chardonnay|riesling|sauvignon|semillon|chablis|meursault|montrachet|corton charlemagne)\b', low): t = 'White'
    if t == 'White' and re.search(r'\b(rouge|rosso|pinot noir|cabernet|merlot|syrah|shiraz|nebbiolo|barolo|barbaresco|brunello)\b', low): t = 'Red'
    if re.search(r'\b(rose|rosato)\b', low): t = 'Rose'
    if re.search(r'\b(port|porto|vintage port|tawny|colheita|madeira)\b', low): t = 'Fortified'
    if cat == 'Whiskies & Spirits': t = 'Spirits'
    size, pack = VN_FMT.get(fmt, (750, 1))
    if re.search(r'\bmag\b', fmt.lower()) and size == 750: size = 1500
    v = vint.strip().upper() if vint else vintage_of(nm)
    if v == 'NV' or not v: v = 'NV' if t in ('Sparkling','Fortified','Spirits') else ''
    if v and v != 'NV' and v not in nm: nm = f'{nm} {v}'
    r2 = infer_region(nm) or reg
    cty = REGION_COUNTRY.get(r2, '') or REGION_COUNTRY.get(reg, '')
    q = int(qty) if str(qty).isdigit() else 1
    items.append(dict(src='vinum', name=nm, type=t, country=cty, region=r2, vintage=v, size=size, pack=pack,
        price=price, compare=None, in_stock=q > 0, stock=2 if q > 0 else 0,
        url='https://vinumfinewines.sg/#'+re.sub(r'[^a-z0-9]+','-',f'{vint} {wine} {fmt}'.lower()).strip('-'), img=vinum_image(wine), rating='', producer=''))

# Wine Culture: [name, id, permalink, price, regular, sale, in_stock, cats, img, short_description]
WC_REG = {'Burgundy':'Burgundy','Bordeaux':'Bordeaux','Rhone Valley':'Rhone','Champagne':'Champagne','Alsace':'Alsace','Loire':'Loire','Provence':'Provence',
          'Italy':'Other Italy','USA':'USA','Australia':'Australia','New Zealand':'New Zealand','Austria':'Austria','Germany':'Germany','Chile':'Chile','Spain':'Spain'}
for r in wc:
    name, pid, url, price, regular, sale, stock, cats, img, sd = r
    sd = html.unescape(sd)
    m = re.search(r'Selection:\s*([A-Za-z ]+?)\s*[–-]\s*([\d.]+)\s*(ml|cl|l)\b', sd, re.I)
    colour = (m.group(1).strip().lower() if m else '')
    size = 750
    if m:
        v = float(m.group(2)); u = m.group(3).lower()
        size = int(round(v if u == 'ml' else v * 10 if u == 'cl' else v * 1000))
    mv = re.search(r'\(\s*((?:19|20)\d\d|NV)\s*\)', sd, re.I)
    vint = mv.group(1).upper() if mv else vintage_of(name)
    ms = re.search(r'Score:\s*(\d{2,3}(?:-\d{2,3})?\+?)', sd)
    rating = f'Score {ms.group(1)}' if ms else ''
    nm = clean(name)
    if vint and vint != 'NV' and vint not in nm: nm = f'{nm} {vint}'
    if size != 750 and not re.search(r'\d+\s*(ml|cl|l)\b', nm.lower()): nm = f'{nm} {size}ml' if size < 1000 else f'{nm} {size/1000:g}L'
    t = {'red':'Red','white':'White','rose':'Rose','sparkling':'Sparkling','champagne':'Sparkling','sweet':'Dessert','dessert':'Dessert','fortified':'Fortified'}.get(colour) or infer_type(nm)
    if 'Champagne' in cats: t = 'Sparkling'
    reg = infer_region(nm) or next((WC_REG[c] for c in cats.split('|') if c in WC_REG), '')
    cty = REGION_COUNTRY.get(reg, '')
    GST = 1.09   # Wine Culture lists prices excluding GST; every other source is GST-inclusive
    p = round(float(price) / 100 * GST) if price else None
    rg = round(float(regular) / 100 * GST) if regular else None
    items.append(dict(src='wineculture', name=nm, type=t, country=cty, region=reg, vintage=vint or '', size=size, pack=pack_of(nm),
        price=p, compare=rg if rg and p and rg > p else None, in_stock=bool(stock), stock=2 if stock else 0,
        url=url, img=img or '', rating=rating, producer=''))

# ---------- Shopify sites (generic feed): [title, handle, product_type, vendor, tags, vtitle, opt1, opt2, price, compare, available, img] ----------
def _load(name):
    p = RAW / name
    return json.load(open(p)) if p.exists() else []

def _variant_slug(vt):
    return re.sub(r'[^a-z0-9]+', '-', (vt or '').lower()).strip('-')

def _size_from_text(s, default=750):
    """'1.5 L', '750ml', '70cl', '375ML', '1.5 ml' (Angra typo for 1.5 L) -> ml"""
    m = re.search(r'(\d+(?:\.\d+)?)\s*(ml|cl|l)\b', (s or '').lower())
    if not m: return default
    v = float(m.group(1)); u = m.group(2)
    if u == 'ml' and v < 10: u = 'l'
    return int(round(v if u == 'ml' else v * 10 if u == 'cl' else v * 1000))

def _default_size(t):
    return 720 if t == 'Sake' else 700 if t == 'Spirits' else 750

def _add_size(nm, size):
    if size != 750 and not re.search(r'\d+(?:\.\d+)?\s*(ml|cl|l)\b', nm.lower()) and not re.search(r'\b(magnum|jeroboam|imperial|methuselah|half bottle)\b', nm.lower()):
        nm = f'{nm} {size}ml' if size < 1000 else f'{nm} {size/1000:g}L'
    return nm

COUNTRY_SET = {'France','Italy','Spain','Germany','Australia','New Zealand','Chile','Argentina','Japan','Portugal','Austria','South Africa','USA','China','Uruguay','Lebanon','Canada','Greece','Hungary','England','Scotland','Israel','Switzerland','Slovenia','Croatia','Georgia','Mexico','Ireland','Jamaica','Barbados','Cuba','Taiwan','India'}
TAG_TYPE = {'red wine':'Red','red':'Red','white wine':'White','white':'White','rose':'Rose','rosé':'Rose','rose wine':'Rose','rosé wine':'Rose',
            'sparkling':'Sparkling','sparkling wine':'Sparkling','champagne':'Sparkling','champagne & sparkling wine':'Sparkling','bubbly':'Sparkling',
            'sweet':'Dessert','sweet wine':'Dessert','dessert':'Dessert','dessert wine':'Dessert','sparkling sweet':'Sparkling',
            'fortified':'Fortified','fortified wine':'Fortified','port':'Fortified','port wine':'Fortified','sherry':'Fortified',
            'spirits':'Spirits','spirit':'Spirits','whisky':'Spirits','whiskey':'Spirits','gin':'Spirits','rum':'Spirits','vodka':'Spirits','cognac':'Spirits','brandy':'Spirits','tequila':'Spirits','liqueur':'Spirits','liqueurs':'Spirits','bai jiu':'Spirits','baijiu':'Spirits',
            'sake':'Sake','orange':'Other','orange wine':'Other','cider':'Other','beer':'Other','alcohol-free wine':'Non-Alcoholic','naa':'Non-Alcoholic'}
SKIP_TYPE = {'event','events','wine dinner','gift cards','gift card','accessories','accessory','glassware','gifts','gift','fridge','water','hampers','sparkling tea','mixer','delivery charge','general','wine chiller','cigar humidor','donation','olive oil'}

def _finish(src, nm, t, cty, reg, vint, size, pack, price, compare, avail, url, img, rating='', producer=''):
    p = float(price) if price not in (None, '') else None
    c = float(compare) if compare not in (None, '') else None
    nm = re.sub(r'\s+', ' ', nm).strip(' ,.;-')
    if vint == 'NV' and re.search(r'\bvintage\b', nm, re.I) and not re.search(r'\bnon[ -]?vintage\b|\bNV\b', nm, re.I):
        vint = ''   # "Vintage Brut" with no year given: year unknown, not NV
    items.append(dict(src=src, name=nm, type=t, country=cty, region=reg, vintage=vint or '', size=size, pack=pack,
        price=p, compare=c if c and p and c > p else None, in_stock=bool(avail), stock=(2 if p else 1) if avail else 0,
        url=url, img=img or '', rating=rating, producer=producer))

# 1855 The Bottle Shop: tags carry vintage/country/region/type; title ends "2020 750ml"
for r in _load('sh_1855.json'):
    title, handle, ptype, vendor, tags, vt, o1, o2, price, compare, avail, img = r
    tg = [x.strip() for x in tags.split('|') if x.strip()]
    tl = {x.lower() for x in tg}
    if tl & {'event','accessories','glass','gift card','hamper'} or 'Wine Dinner' in title or '|' in title: continue
    if not (tl & {'wine','spirits','sake','champagne','beer'}): continue
    if re.search(r'\bbundle\b|\bset of\b', title.lower()): continue
    t = next((TAG_TYPE[x] for x in ('red wine','white wine','champagne','sparkling','rose','sweet','dessert','fortified','sake','spirits') if x in tl), '')
    nm = clean(title)
    if not t: t = infer_type(nm)
    if t == 'Spirits' and 'sake' in tl: t = 'Sake'
    vint = next((x for x in tg if re.fullmatch(r'(19|20)\d\d', x)), '') or vintage_of(nm)
    if t in ('Sparkling','Spirits','Fortified') and not vint: vint = 'NV'
    size = size_of(nm, _default_size(t))
    if 'half bottle' in tl and size == 750: size = 375
    if 'magnum' in tl and size == 750: size = 1500
    cty = next((x for x in tg if x in COUNTRY_SET), '')
    reg = infer_region(nm) or next(({'Bordeaux':'Bordeaux','Burgundy':'Burgundy','Champagne':'Champagne','Rhone':'Rhone','Loire':'Loire','Alsace':'Alsace','Tuscany':'Tuscany','Piedmont':'Piedmont','Veneto':'Veneto','Sicily':'Sicily'}[x] for x in tg if x in ('Bordeaux','Burgundy','Champagne','Rhone','Loire','Alsace','Tuscany','Piedmont','Veneto','Sicily')), '')
    _finish('1855', nm, t, cty, reg, vint, size, pack_of(nm), price, compare, avail,
            'https://www.1855thebottleshop.com/products/' + handle, img, producer='')

# The Straits Wine Company: product_type Red/White/...; vintage in title
ST_TYPE = {'Red':'Red','White':'White','Rose':'Rose','Sparkling':'Sparkling','Sweet':'Dessert','Cider':'Other','Liqueur':'Spirits','Gin':'Spirits','Whisky':'Spirits','Sake':'Sake'}
for r in _load('sh_straits.json'):
    title, handle, ptype, vendor, tags, vt, o1, o2, price, compare, avail, img = r
    if ptype not in ST_TYPE: continue
    nm = clean(re.sub(r'^\[[^\]]*\]\s*', '', title))
    t = ST_TYPE[ptype]
    vint = vintage_of(nm) or ('NV' if t in ('Sparkling','Spirits') else '')
    size = size_of(nm, _default_size(t))
    _finish('straits', nm, t, '', infer_region(nm + ' ' + vendor), vint, size, pack_of(nm), price, compare, avail,
            'https://straitswine.com/products/' + handle, img, producer=clean(vendor))

# Wine Connection: title "PRODUCER "Cuvee" 2019 - Wine - Region - Country"
WCN_TYPE = {'Red Wine':'Red','White Wine':'White','Rosé Wine':'Rose','Champagne & Sparkling Wine':'Sparkling','Sweet Wine':'Dessert','Port Wine':'Fortified',
            'Spirit':'Spirits','Sake':'Sake','Cider':'Other','Orange Wine':'Other','Alcohol-Free Wine':'Non-Alcoholic'}
for r in _load('sh_wineconn.json'):
    title, handle, ptype, vendor, tags, vt, o1, o2, price, compare, avail, img = r
    if ptype not in WCN_TYPE or vt not in ('Default Title', ''): continue
    t = WCN_TYPE[ptype]
    parts = [p.strip() for p in clean(title).split(' - ')]
    head = parts[0]
    vint = vintage_of(head) or ('NV' if t in ('Sparkling','Spirits','Fortified') else '')
    head_nov = VINT_RE.sub('', head).strip()
    prod = title_case(head_nov) if head_nov.isupper() or re.match(r'^[A-Z0-9 &\'".-]+$', head_nov) else head_nov
    wine = parts[1] if len(parts) > 2 else ''
    cty = parts[-1] if len(parts) > 1 and parts[-1] in COUNTRY_SET else ''
    region_hint = parts[2] if len(parts) > 3 else ''
    nm = ' '.join(x for x in (prod, wine, vint if vint and vint != 'NV' else '') if x)
    nm = nm.replace('"', '')
    size = _size_from_text(next((x for x in tags.split('|') if x.startswith('packing:')), ''), _default_size(t))
    size = size_of(nm, size)
    rating = ''
    acc = [x.split(':', 1)[1] for x in tags.split('|') if x.startswith('Accolades:')]
    reg = infer_region(nm + ' ' + region_hint) or infer_region(region_hint)
    _finish('wineconn', nm, t, cty, reg, vint, size, pack_of(nm), price, compare, avail,
            'https://www.wineconnection.com.sg/products/' + handle, img, producer=prod)

# Wines Wholesales: product_type = country (or Gifts/Fridge/...); tags carry colour + size; vintage rarely given
for r in _load('sh_wholesale.json'):
    title, handle, ptype, vendor, tags, vt, o1, o2, price, compare, avail, img = r
    if ptype.lower() in SKIP_TYPE or not ptype: continue
    tg = [x.strip() for x in tags.split('|') if x.strip()]
    tl = {x.lower() for x in tg}
    if ptype == 'Whisky' or ptype == 'Bai Jiu': t = 'Spirits'
    elif ptype == 'Beer': t = 'Other'
    else: t = next((TAG_TYPE[x] for x in ('port','fortified','sparkling sweet','sparkling','sweet','rosé','rose','white','red') if x in tl), '')
    nm = clean(title)
    if re.search(r'\b(gift set|with \d+ (flutes|glasses)|hamper|bundle)\b', nm.lower()): continue
    if not t: t = infer_type(nm)
    vint = (o1 if re.fullmatch(r'(19|20)\d\d', o1 or '') else '') or vintage_of(nm) or ('NV' if t in ('Sparkling','Fortified','Spirits') else '')
    if vint and vint != 'NV' and vint not in nm: nm = f'{nm} {vint}'
    size = _size_from_text(next((x for x in tg if re.fullmatch(r'\d+(\.\d+)?\s*(ml|l)', x.lower())), ''), _default_size(t))
    size = size_of(nm, size)
    cty = ptype if ptype in COUNTRY_SET else ''
    url = 'https://www.wineswholesales.com.sg/products/' + handle + ('' if vt in ('Default Title', '') else '?variant=' + _variant_slug(vt))
    _finish('wholesale', nm, t, cty, infer_region(nm), vint, size, pack_of(nm), price, compare, avail, url, img)

# Wines Online: product_type WINE/CHAMPAGNE/WHISKY/...; tags type-Red, vintage-2023, country-France, region-X, ratings-WS-92, cap-70cl
WO_TYPE = {'WINE':'', 'CHAMPAGNE':'Sparkling', 'WHISKY':'Spirits', 'GIN':'Spirits', 'SAKE':'Sake', 'RUM':'Spirits', 'VODKA':'Spirits', 'COGNAC':'Spirits', 'BRANDY':'Spirits', 'LIQUEUR':'Spirits', 'NAA':'Non-Alcoholic', 'BEER CIDER':'Other'}
WO_CRITIC = {'WS':'Wine Spectator','RP':'Robert Parker','WA':'Robert Parker','JS':'James Suckling','JH':'James Halliday','D':'Decanter','V':'Vinous','AG':'Vinous','JR':'Jancis Robinson','WE':'Wine Enthusiast','BH':'Burghound','JD':'Jeb Dunnuck','TA':'Tim Atkin'}
for r in _load('sh_winesonl.json'):
    title, handle, ptype, vendor, tags, vt, o1, o2, price, compare, avail, img = r
    if ptype not in WO_TYPE: continue
    tg = [x.strip() for x in tags.split('|') if x.strip()]
    tagv = {}
    for x in tg:
        m = re.match(r'^(type|vintage|country|region|ratings|cap|size)-(.+)$', x, re.I)
        if m: tagv.setdefault(m.group(1).lower(), []).append(m.group(2).replace('-', ' ').strip())
    if 'gift' in {x.lower() for x in tg} or '+ $' in vt: continue
    pack = 1
    m = re.match(r'^(\d+)\s*bottles?$', vt.lower())
    if m: pack = int(m.group(1))
    elif vt not in ('Default Title', '', '1 Bottle'): continue
    t = WO_TYPE[ptype] or TAG_TYPE.get((tagv.get('type') or [''])[0].lower(), '')
    nm = clean(re.sub(r'\s*\((\d+(?:\.\d+)?\s*(?:ml|cl|l))\)', r' \1', title, flags=re.I))
    if not t: t = infer_type(nm)
    vint = vintage_of(nm) or (tagv.get('vintage') or [''])[0]
    if not re.fullmatch(r'((19|20)\d\d|NV)', vint): vint = 'NV' if t in ('Sparkling','Spirits','Fortified') else ''
    if vint and vint != 'NV' and vint not in nm: nm = f'{nm} {vint}'
    size = size_of(nm, _size_from_text((tagv.get('cap') or [''])[0], _default_size(t)))
    cty = norm_country((tagv.get('country') or [''])[0])
    cty = cty if cty in COUNTRY_SET else ''
    reg = infer_region(nm) or infer_region((tagv.get('region') or [''])[0])
    rating = ' / '.join(f"{a} {b}" for a, b in (x.split(' ', 1) for x in tagv.get('ratings', []) if ' ' in x) if re.match(r'^\d{2,3}', b))
    url = 'https://winesonline.com.sg/products/' + handle + ('' if pack == 1 else '?variant=' + _variant_slug(vt))
    mp = re.search(r'pay\s*\d+\s*get\s*(\d+)', nm.lower())
    pack = max(pack, pack_of(nm), int(mp.group(1)) if mp else 1)
    _finish('winesonl', nm, t, cty, reg, vint, size, pack, price, compare, avail, url, img, rating=rating)

# Angra: product_type RED/WHITE/...; options VINTAGE + SIZE ("2024 / 750 ml"); titles in caps
AN_TYPE = {'RED':'Red','WHITE':'White','CHAMPAGNE':'Sparkling','SPARKLING':'Sparkling','ROSE':'Rose','FORTIFIED':'Fortified','SWEET':'Dessert','SWEET WINE':'Dessert','DESSERT':'Dessert',
           'LIQUEUR':'Spirits','Liqueurs':'Spirits','Cognac':'Spirits','WHISKY':'Spirits','SPIRIT':'Spirits','TEQUILA':'Spirits','SAKE':'Sake','BEER':'Other','Orange':'Other'}
for r in _load('sh_angra.json'):
    title, handle, ptype, vendor, tags, vt, o1, o2, price, compare, avail, img = r
    if ptype not in AN_TYPE: continue
    t = AN_TYPE[ptype]
    nm = title_case(clean(title))
    nm = re.sub(r'\s*\(.*?pre-?order.*?\)', '', nm, flags=re.I)
    vint = o1.strip().upper() if re.fullmatch(r'((19|20)\d\d|NV)', (o1 or '').strip(), re.I) else vintage_of(nm) or ('NV' if t in ('Sparkling','Spirits','Fortified') else '')
    if vint and vint != 'NV' and vint not in nm: nm = f'{nm} {vint}'
    size = _size_from_text(o2, 0) or size_of(nm, _default_size(t))
    nm = _add_size(nm, size)
    tg = [x.strip() for x in tags.split('|') if x.strip()]
    cty = next((x for x in tg if x in COUNTRY_SET), '')
    reg = infer_region(nm + ' ' + vendor) or next((x for x in tg if x in REGION_COUNTRY), '')
    rating = ''
    m = re.search(r'\b(\d{2,3}\+?)\s*(RP|JS|WS|WA|JD|V|AG|D)\b', vt)
    if m: rating = f"{m.group(2)} {m.group(1)}"
    url = 'https://angra.com.sg/products/' + handle + ('' if vt in ('Default Title', '') else '?variant=' + _variant_slug(vt))
    _finish('angra', nm, t, cty, reg, vint, size, pack_of(nm), price, compare, avail, url, img, rating=rating, producer=title_case(clean(vendor)))

# Ponti Wine Cellars: [title, handle, price, compare, sold_out, image, tags, description]
# tags e.g. "All items|Vintage Wine|1994|750ml|Monbousquet|Red|Bordeaux|France"; description "Vintage - 1994Country - France...Ratings - WA90"
PO_CRITIC = {'WA':'Robert Parker','RP':'Robert Parker','JS':'James Suckling','WS':'Wine Spectator','V':'Vinous','AG':'Vinous','JR':'Jancis Robinson','D':'Decanter','WE':'Wine Enthusiast','BH':'Burghound','JD':'Jeb Dunnuck','JH':'James Halliday'}
for r in _load('ponti_all.json'):
    title, handle, price, compare, sold, img, tags, desc = r
    tg = [x.strip() for x in (tags or '').split('|') if x.strip()]
    tl = {x.lower() for x in tg}
    nm = clean(title)
    low = nm.lower()
    if re.search(r'\b(gift card|voucher|glass|decanter|corkscrew|opener|accessor|set of)\b', low) or tl & {'accessories','gift card','glassware'}: continue
    t = next((TAG_TYPE[x] for x in ('red','white','rose','rosé','sparkling','champagne','sweet','dessert','fortified','port','spirits','whisky','sake') if x in tl), '') or infer_type(nm)
    m = re.search(r'Vintage\s*-\s*((?:19|20)\d\d|NV)', desc or '', re.I)
    vint = (m.group(1).upper() if m else '') or next((x for x in tg if re.fullmatch(r'(19|20)\d\d', x)), '') or vintage_of(nm)
    if not vint and t in ('Sparkling','Spirits','Fortified'): vint = 'NV'
    if vint and vint != 'NV' and vint not in nm: nm = f'{nm} {vint}'
    m = re.search(r'Size\s*-\s*([\d.]+\s*(?:ml|cl|l))', desc or '', re.I)
    size = _size_from_text(m.group(1), 0) if m else 0
    if not size: size = _size_from_text(next((x for x in tg if re.fullmatch(r'[\d.]+\s*(ml|cl|l)', x.lower())), ''), 0)
    if not size: size = size_of(nm, _default_size(t))
    nm = _add_size(nm, size)
    m = re.search(r'Country\s*-\s*([A-Za-z ]+?)\s*(?:Region|Size|Grape|Ratings|SKU|$)', desc or '')
    cty = norm_country(m.group(1)) if m else next((x for x in tg if x in COUNTRY_SET), '')
    if cty not in COUNTRY_SET: cty = ''
    m = re.search(r'Region\s*-\s*([A-Za-z ,\'-]+?)\s*(?:Size|Grape|Ratings|SKU|$)', desc or '')
    reg = infer_region(nm) or infer_region(m.group(1) if m else '') or next((x for x in tg if x in REGION_COUNTRY), '')
    rating = ''
    m = re.search(r'Ratings?\s*-\s*([A-Z]{1,2})\s*(\d{2,3}\+?)', desc or '')
    if m: rating = f"{m.group(1)} {m.group(2)}"
    _finish('ponti', nm, t, cty, reg, vint, size, pack_of(nm), price, compare, not sold,
            'https://pontiwinecellars.com.sg/products/' + handle, img, rating=rating)

# Winehours: [name, url, price, old_price, out_of_stock, ratings('WA 100|JS 98'), image, enquire]
WH_CRITIC = {'WA':'Robert Parker','RP':'Robert Parker','JS':'James Suckling','WS':'Wine Spectator','V':'Vinous','Vinious':'Vinous','Vinous':'Vinous','AG':'Vinous','JR':'Jancis Robinson','D':'Decanter','Decanter':'Decanter','WE':'Wine Enthusiast','BH':'Burghound','JD':'Jeb Dunnuck','JH':'James Halliday','IWC':'IWC','W&S':'Wine & Spirits','TA':'Tim Atkin'}
for r in _load('wh_all.json'):
    name, url, price, old, oos, rt, img, enquire = r
    nm = clean(name)
    low = nm.lower()
    if re.search(r'\b(gift card|voucher|glass|decanter|aroma|accessor)\b', low): continue
    folder = unquote(img or '').split('/catalog/')[-1].rsplit('/', 1)[0].split('/')[-1].lower()
    if folder in ('mix 2-3', 'mix 6', 'bulk', 'duo hampers holiday', 'duo', 'best seller template'): continue   # multi-bottle sets
    if re.match(r'^(buy \d+|duo|trio|quad|quartet|mix(ed)?)\b', low) or re.search(r'\b(bundle|gift set|hamper|celebration|holiday season|appelation mix|appellation mix)\b', low): continue
    nm = re.sub(r'^(nv|n\.v\.)\s+', '', nm, flags=re.I)
    nm = re.sub(r'^((?:19|20)\d\d)\s+(.+)$', r'\2 \1', nm)       # "2022 Catena Zapata" -> "Catena Zapata 2022"
    if price is not None and price <= 2: price = None           # S$1.00 placeholder on unavailable items
    t = infer_type(nm)
    vint = vintage_of(nm) or ('NV' if t in ('Sparkling','Spirits','Fortified') else '')
    size = size_of(nm, _default_size(t))
    pack = pack_of(nm)
    nm = re.sub(r'\s+with gift box$', ' (Gift Box)', nm, flags=re.I)
    rating = ' / '.join(f"{a} {b}" for a, b in (x.rsplit(' ', 1) for x in rt.split('|') if ' ' in x) if re.match(r'^\d{2,3}', b))
    if enquire:
        items.append(dict(src='winehours', name=nm, type=t, country='', region=infer_region(nm), vintage=vint, size=size, pack=pack,
            price=None, compare=None, in_stock=False, stock=1, url=url, img=img or '', rating=rating, producer=''))
    else:
        _finish('winehours', nm, t, '', infer_region(nm), vint, size, pack, price, old, not oos, url, img, rating=rating)

# Bottles & Bottles: [category, brand, title, url, price, old_price, image, stock_text, country, region]
BNB_TYPE = {'red':'Red','white':'White','sweet':'Dessert','rose':'Rose','nonalc':'Non-Alcoholic','sparkling':'Sparkling','spirits':'Spirits','wine':''}
_bnb_type = {}
for r in _load('bnb_all.json'):
    cat, brand, title, url, price, old, img, stock_text, cty, reg = r
    if url not in _bnb_type or not _bnb_type[url]: _bnb_type[url] = BNB_TYPE.get(cat, '')
_bnb_seen = set()
for r in _load('bnb_all.json'):
    cat, brand, title, url, price, old, img, stock_text, cty, reg = r
    if url in _bnb_seen: continue
    _bnb_seen.add(url)
    nm = clean(title).strip(' ,.;-')
    low = nm.lower()
    if re.search(r'\b(gift set|hamper|bundle|glass|decanter|voucher)\b', low): continue
    t = _bnb_type.get(url) or infer_type(nm)
    if t == 'Spirits' and re.search(r'\bsake\b', low): t = 'Sake'
    if t == 'Spirits' and re.search(r'\b(port|sherry|madeira)\b', low): t = 'Fortified'
    vint = vintage_of(nm) or ('NV' if t in ('Sparkling','Spirits','Fortified') else '')
    size = size_of(nm, _default_size(t))
    st = (stock_text or '').lower()
    avail = not re.search(r'out of stock', st)
    stock = 0 if not avail else (1 if 'pre' in st else 2)
    cty = norm_country(cty) if cty else ''
    if cty not in COUNTRY_SET: cty = ''
    region = infer_region(nm + ' ' + (reg or '')) or ''
    items.append(dict(src='bnb', name=nm, type=t, country=cty, region=region, vintage=vint, size=size, pack=pack_of(nm),
        price=float(price) if price else None, compare=float(old) if old and price and float(old) > float(price) else None,
        in_stock=avail, stock=stock, url=url, img=img or '', rating='', producer=clean(brand)))

for it in items:
    if not it['region']:
        it['region'] = infer_region(it['name'])
    if not it['country'] and it['region']:
        it['country'] = REGION_COUNTRY.get(it['region'], '')
    if it['region'] == it['country'] and it['country'] in ('Spain','Germany','USA','Australia','New Zealand','Chile','Argentina','Portugal','South Africa','Austria','Scotland','Japan'):
        pass
    it['tok'] = tokens(it['name'])

print('normalised', len(items), collections.Counter(i['src'] for i in items))

# ---------- dedupe ----------
NOISE = {'pauillac','margaux','saint','st','julien','estephe','emilion','pomerol','pessac','leognan','graves','medoc','bordeaux',
 'burgundy','bourgogne','champagne','brut','rioja','ribera','duero','toscana','tuscany','igt','doc','docg','classico','superiore',
 'grand','cru','classe','1er','premier','rothschild','nv','ex','chateau','ch','domaine','dom','famille','vineyard','vineyards',
 'winery','estate','cellars','ngbx','gbx','owc','occ','box','gift','case','bottle','bottles','napa','valley','marlborough','barossa',
 'mendoza','maipo','montalcino','bolgheri','langhe','alba','piemonte','piedmont','veneto','valpolicella','marchesi','tenuta','dell',
 'chateauneuf','pape','cdp','rhone','cotes','du','de','la','le','les','des','sg','singapore','wine','wines','vintage','gran','mc','longueville','haut','medoc','special','signature'}
for it in items:
    nm = it['name']
    if it['src'] == 'pivene':
        nm = re.sub(r"\s-\s[A-Za-z' ]+?(?=\s\(|\s(?:19|20)\d\d|\sNV|$)", '', nm)
        it['tok'] = tokens(nm)
    it['prod'] = set()
    if it['src'] == 'pivene' and ', ' in nm:
        prod, core = nm.split(', ', 1)
        c = tokens(core) - NOISE
        it['core'] = c or tokens(core) or it['tok']
        it['prod'] = tokens(prod)
    else:
        it['core'] = (it['tok'] - NOISE) or it['tok']

APPELL = {'pauillac','margaux','julien','estephe','emilion','pomerol','pessac','leognan','graves','medoc','listrac','moulis','fronsac','castillon'}
# appellation words that never co-occur on one label: two listings naming different ones are different wines
APPELL_KEY = {'chateauneuf':'cndp','pape':'cndp','cdp':'cndp','gigondas':'gigondas','vacqueyras':'vacqueyras','rasteau':'rasteau','cairanne':'cairanne',
              'hermitage':'hermitage','crozes':'crozes','cornas':'cornas','rotie':'rotie','condrieu':'condrieu','rhone':'rhone','ventoux':'ventoux','lirac':'lirac',
              'montalcino':'montalcino','bolgheri':'bolgheri','chianti':'chianti','montepulciano':'montepulciano','barolo':'barolo','barbaresco':'barbaresco','langhe':'langhe','roero':'roero',
              'rioja':'rioja','ribera':'ribera','priorat':'priorat','toro':'toro','rueda':'rueda',
              'gevrey':'gevrey','chambertin':'chambertin','chambolle':'chambolle','musigny':'musigny','vosne':'vosne','nuits':'nuits','morey':'morey','vougeot':'vougeot','echezeaux':'echezeaux','grandsechezeaux':'grandsechezeaux',
              'meursault':'meursault','puligny':'puligny','chassagne':'chassagne','montrachet':'montrachet','pommard':'pommard','volnay':'volnay','beaune':'beaune','corton':'corton','charlemagne':'charlemagne','chablis':'chablis','santenay':'santenay','marsannay':'marsannay','fixin':'fixin','savigny':'savigny','pernand':'pernand','aloxe':'aloxe','mercurey':'mercurey','rully':'rully','givry':'givry','macon':'macon','fuisse':'fuisse',
              'sancerre':'sancerre','fume':'fume','vouvray':'vouvray','chinon':'chinon','napa':'napa','sonoma':'sonoma','barossa':'barossa','mclaren':'mclaren','coonawarra':'coonawarra','marlborough':'marlborough','otago':'otago','mosel':'mosel','rheingau':'rheingau','pfalz':'pfalz','nahe':'nahe'}
def _appell(toks):
    return {APPELL_KEY[t] for t in toks if t in APPELL_KEY} - ({'rhone'} if {'cndp','gigondas','vacqueyras','hermitage','crozes','cornas','rotie','condrieu','rasteau','cairanne','ventoux','lirac'} & {APPELL_KEY[t] for t in toks if t in APPELL_KEY} else set())

def compatible(a, b):
    if a['src'] == b['src']: return False
    if a['vintage'] != b['vintage'] or a['size'] != b['size'] or a['pack'] != b['pack']: return False
    if a['type'] != b['type'] and 'Other' not in (a['type'], b['type']): return False
    fa, fb, ca, cb = a['tok'], b['tok'], a['core'], b['core']
    if not ca or not cb: return False
    aa, ab = fa & APPELL, fb & APPELL
    if aa and ab and aa != ab: return False   # e.g. Lagrange (Pomerol) vs Lagrange (St Julien)
    ka, kb = _appell(fa), _appell(fb)
    if ka and kb and ka != kb: return False   # e.g. Guigal Cotes du Rhone vs Guigal Chateauneuf du Pape
    if not (ca <= fb and cb <= fa): return False
    if (fa ^ fb) & SECOND: return False
    extra_a = fa - fb - NOISE - (fa - ca)
    extra_b = fb - fa - NOISE - (fb - cb)
    if extra_a or extra_b: return False
    pa, pb = a['prod'], b['prod']
    if pa and cb == pa and ca != cb: return False   # other item is the producer's main wine, this is a sub-cuvee
    if pb and ca == pb and ca != cb: return False
    if (ca | cb) & SECOND and (ca - pa - pb - NOISE) != (cb - pa - pb - NOISE): return False
    if sum(len(t) for t in (fa & fb)) < 5: return False
    return True

# blocking by (vintage,size,pack)
blocks = collections.defaultdict(list)
for idx, it in enumerate(items):
    blocks[(it['vintage'], it['size'], it['pack'])].append(idx)

parent = list(range(len(items)))
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x
srcs = [{it['src']} for it in items]   # sources present in each root's group
def union(a, b):
    ra, rb = find(a), find(b)
    if ra == rb: return
    if srcs[ra] & srcs[rb]: return         # never two listings from the same merchant in one group
    parent[ra] = rb
    srcs[rb] |= srcs[ra]

pairs = 0
for key, idxs in blocks.items():
    for i, j in itertools.combinations(idxs, 2):
        if compatible(items[i], items[j]):
            union(i, j); pairs += 1
print('matched pairs', pairs)

groups = collections.defaultdict(list)
for idx in range(len(items)):
    groups[find(idx)].append(idx)

SRC_PRIO = {'pivene': 0, 'grandvin': 1, 'cornerstone': 2, 'crystal': 3, 'wineculture': 4, 'vinum': 5, '1855': 6, 'angra': 7, 'wineconn': 8, 'straits': 9, 'winesonl': 10, 'wholesale': 11, 'ponti': 12, 'finewines': 13, 'winehours': 14, 'bnb': 15}
merged = []
for g, idxs in groups.items():
    members = [items[i] for i in idxs]
    priced = [m for m in members if m['price'] is not None]
    best = max(priced, key=lambda m: m['price']) if priced else members[0]
    namer = sorted(members, key=lambda m: (SRC_PRIO[m['src']], -len(m['name'])))[0]
    # remove source-specific size suffix noise from display name
    name = namer['name']
    name = re.sub(r'\s*\((?:GBX|NGBX|W/O LIGHT)\)', '', name, flags=re.I)
    name = re.sub(r'\s+\d+ML$', '', name, flags=re.I)
    name = re.sub(r'\s+', ' ', name).strip()
    types = [m['type'] for m in members if m['type'] != 'Other']
    t = collections.Counter(types).most_common(1)[0][0] if types else 'Other'
    country = next((m['country'] for m in sorted(members, key=lambda m: SRC_PRIO[m['src']]) if m['country']), '')
    region = next((m['region'] for m in sorted(members, key=lambda m: SRC_PRIO[m['src']]) if m['region']), '')
    rating = next((m['rating'] for m in members if m.get('rating')), '')
    note = next((m.get('note') for m in members if m.get('note')), '')
    merged.append(dict(
        id=len(merged)+1, name=name, type=t, country=country, region=region, vintage=best['vintage'],
        size=best['size'], pack=best['pack'], price=best['price'], compare=best['compare'] if best['compare'] and best['price'] and best['compare'] > best['price'] else None,
        in_stock=any(m['in_stock'] for m in members), stock=max(m['stock'] for m in members), rating=rating, note=note,
        sources=[dict(site=m['src'], price=m['price'], url=m['url'], name=m['name'], img=m['img'], stock=m['stock']) for m in sorted(members, key=lambda m: SRC_PRIO[m['src']])],
        img_ref=best['img']))

merged.sort(key=lambda m: (TYPE_ORDER.index(m['type']) if m['type'] in TYPE_ORDER else 99, m['country'], m['region'], m['name'], m['vintage']))
for i, m in enumerate(merged): m['id'] = i+1
print('merged', len(merged), 'from', len(items))
print('multi-source', sum(1 for m in merged if len(m['sources']) > 1))
print(collections.Counter(m['type'] for m in merged))
print(collections.Counter(m['country'] for m in merged).most_common(15))
print('no price', sum(1 for m in merged if m['price'] is None))
json.dump(merged, open(ROOT / 'data' / 'merged.json', 'w'), ensure_ascii=False)

