import json, re, unicodedata, collections, itertools, html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / 'data' / 'raw'
piv = json.load(open(RAW/'pivene_all.json'))
cw = json.load(open(RAW/'cw_all.json'))
cs = json.load(open(RAW/'cs_all.json'))
cs_types = json.load(open(RAW/'cs_types.json'))

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
        if re.match(r'^[a-z]+$', lw) is None and not lw.isalpha():
            out.append(w.upper() if re.match(r'^(nv|igt|doc|docg|aoc|owc|occ|gbx|ngbx|sgn|px|xo|vs|vsop)$', lw) else w)
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
    size = size_of(nm, 700 if t == 'Spirits' else 750)
    pack = pack_of(nm)
    if re.search(r'\(owc 1\)', nm.lower()): pack = 1
    price = op if op is not None else lp
    compare = lp if (op is not None and lp and lp > op) else None
    cty = CS_COUNTRY.get(cat, '')
    reg = infer_region(nm)
    if not cty and reg: cty = REGION_COUNTRY.get(reg, '')
    items.append(dict(src='cornerstone', name=nm, type=t, country=cty, region=reg, vintage=vintage_of(nm), size=size, pack=pack,
        price=price, compare=compare, in_stock=(mode == 'buy'), stock=2 if mode == 'buy' else 1, url='https://shop.cornerstonewines.com'+href, img=img or '',
        rating='', producer=''))

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

def compatible(a, b):
    if a['src'] == b['src']: return False
    if a['vintage'] != b['vintage'] or a['size'] != b['size'] or a['pack'] != b['pack']: return False
    if a['type'] != b['type'] and 'Other' not in (a['type'], b['type']): return False
    fa, fb, ca, cb = a['tok'], b['tok'], a['core'], b['core']
    if not ca or not cb: return False
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
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb: parent[ra] = rb

pairs = 0
for key, idxs in blocks.items():
    for i, j in itertools.combinations(idxs, 2):
        if compatible(items[i], items[j]):
            union(i, j); pairs += 1
print('matched pairs', pairs)

groups = collections.defaultdict(list)
for idx in range(len(items)):
    groups[find(idx)].append(idx)

SRC_PRIO = {'pivene': 0, 'cornerstone': 1, 'crystal': 2}
merged = []
for g, idxs in groups.items():
    members = [items[i] for i in idxs]
    priced = [m for m in members if m['price'] is not None]
    best = max(priced, key=lambda m: m['price']) if priced else members[0]
    namer = sorted(members, key=lambda m: (SRC_PRIO[m['src']], -len(m['name'])))[0]
    # remove source-specific size suffix noise from display name
    name = namer['name']
    name = re.sub(r'\s*\((?:GBX|NGBX|W/O LIGHT)\)', '', name, flags=re.I)
    name = re.sub(r'\s+\d+ML$', '', name)
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

