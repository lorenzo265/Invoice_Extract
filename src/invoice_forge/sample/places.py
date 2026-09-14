"""Where the fictional companies are, and the words each language builds them from.

Tables only, so `parties.py` stays the logic. The stems are invented: they are the kind
of word a place is named after in that language, and none of them names a company that
exists. Cities and legal forms are real, because they are not anybody's property — a
street in Göteborg and the letters `AB` identify no one.

Every table is keyed by language or by country, and `tests/forge/unit/test_places.py`
holds them to the profiles: a profile whose language or country no table covers would be
a document printed in the wrong words, and English is a fallback that hides it.
"""

from __future__ import annotations

from collections.abc import Mapping

# Six invented stems per language, each a place-shaped word of that language.
STEMS: Mapping[str, tuple[str, ...]] = {
    "cs": ("Vltavín", "Lipohrad", "Skalnice", "Březovka", "Jasanov", "Kamenec"),
    "da": ("Fjordborg", "Strandgård", "Bøgelund", "Havnebro", "Klintved", "Sølvbæk"),
    "de": ("Rheinwerk", "Nordlicht", "Elbtal", "Schwarzbach", "Hafenkante", "Sturmfels"),
    "el": ("Αστερίας", "Ελαιώνας", "Θαλασσιά", "Πετρανθή", "Κυματίς", "Ορεινός"),
    "en": ("Ashcroft", "Wearside", "Kestrel", "Mallowfield", "Brackenhill", "Thornby"),
    "es": ("Valdearena", "Peñalta", "Montenar", "Riobranco", "Sierrablanca", "Olivalta"),
    "fi": ("Koivuranta", "Järvelä", "Salmikoski", "Hiekkaniemi", "Tuulimäki", "Kivipelto"),
    "fr": ("Valmont", "Bellerive", "Clairbois", "Hautfort", "Rivegauche", "Montclair"),
    "it": ("Valdoro", "Montelario", "Pietrabella", "Fontesca", "Colledoro", "Marinalta"),
    "nl": ("Duinzicht", "Havenkade", "Meerbeek", "Lindehof", "Vaartzicht", "Rietvoorde"),
    "no": ("Fjellvik", "Nordlys", "Bjørkdal", "Havnely", "Fossheim", "Granlia"),
    "pl": ("Dąbrowiec", "Jaworzyn", "Bielawka", "Sosnolin", "Wiślanka", "Górnolesie"),
    "pt": ("Valdoreste", "Serrafria", "Ribamonte", "Pinhalta", "Marvela", "Castelnovo"),
    "sk": ("Tatranec", "Hronovec", "Lipovina", "Javorec", "Dunajka", "Bystrina"),
    "sv": ("Fjordvik", "Bergslund", "Strandby", "Norrsken", "Almvik", "Tallhöjd"),
    "tr": ("Yıldıztepe", "Gökçeler", "Denizkent", "Çamlıova", "Mavikent", "Ardaçlı"),
}

TRADES: Mapping[str, tuple[str, ...]] = {
    "cs": ("Komponenty", "Průmyslové Dodávky", "Systémy", "Technologie", "Obchod"),
    "da": ("Komponenter", "Industrileverancer", "Systemer", "Teknologi", "Handel"),
    "de": ("Industriebedarf", "Technik", "Handelsgesellschaft", "Systeme", "Elektronik"),
    "el": ("Εξαρτήματα", "Βιομηχανικά Εφόδια", "Συστήματα", "Τεχνολογίες", "Εμπορική"),
    "en": ("Components", "Industrial Supplies", "Systems", "Technologies", "Trading"),
    "es": ("Componentes", "Suministros Industriales", "Sistemas", "Tecnologías", "Comercial"),
    "fi": ("Komponentit", "Teollisuustarvike", "Järjestelmät", "Teknologia", "Kauppa"),
    "fr": ("Composants", "Fournitures Industrielles", "Systèmes", "Technologies"),
    "it": ("Componenti", "Forniture Industriali", "Sistemi", "Tecnologie", "Commerciale"),
    "nl": ("Componenten", "Industriële Toelevering", "Systemen", "Technologie", "Handel"),
    "no": ("Komponenter", "Industrileveranser", "Systemer", "Teknologi", "Handel"),
    "pl": ("Komponenty", "Zaopatrzenie Przemysłowe", "Systemy", "Technologie", "Handel"),
    "pt": ("Componentes", "Fornecimentos Industriais", "Sistemas", "Tecnologias", "Comércio"),
    "sk": ("Komponenty", "Priemyselné Dodávky", "Systémy", "Technológie", "Obchod"),
    "sv": ("Elektronik", "Industri", "System", "Teknik", "Handel"),
    "tr": ("Bileşenler", "Endüstriyel Malzeme", "Sistemler", "Teknoloji", "Ticaret"),
}

STREETS: Mapping[str, tuple[str, ...]] = {
    "cs": ("Přístavní", "Průmyslová", "Lipová", "Tovární", "Dílenská"),
    "da": ("Havnevej", "Industrivej", "Lindeallé", "Fabriksvej", "Værkstedsvej"),
    "de": ("Am Hafen", "Industrieweg", "Lindenstraße", "Gutenbergstraße", "Talweg"),
    "el": ("οδός Λιμένος", "λεωφόρος Βιομηχανίας", "οδός Εργαστηρίων", "οδός Εργοστασίου"),
    "en": ("Foundry Road", "Kestrel Way", "Millbrook Lane", "Harbour Street", "Elm Close"),
    "es": (
        "calle del Puerto",
        "avenida Industrial",
        "calle de los Talleres",
        "camino de la Fábrica",
    ),
    "fi": ("Satamatie", "Teollisuustie", "Lehmuskatu", "Tehtaankatu", "Verstaskatu"),
    "fr": ("rue des Ateliers", "avenue du Port", "chemin des Vignes", "rue Lavoisier"),
    "it": ("via del Porto", "viale Industria", "via delle Officine", "via della Fabbrica"),
    "nl": ("Havenweg", "Industrieweg", "Lindelaan", "Fabrieksstraat", "Vaartkade"),
    "no": ("Havneveien", "Industriveien", "Lindeveien", "Fabrikkveien", "Verkstedveien"),
    "pl": ("ulica Portowa", "ulica Przemysłowa", "ulica Lipowa", "ulica Fabryczna"),
    "pt": ("rua do Porto", "avenida Industrial", "rua das Oficinas", "travessa da Fábrica"),
    "sk": ("Prístavná", "Priemyselná", "Lipová", "Továrenská", "Dielenská"),
    "sv": ("Industrivägen", "Hamngatan", "Verkstadsgatan", "Björkstigen"),
    "tr": ("Liman Caddesi", "Sanayi Caddesi", "Ihlamur Sokak", "Fabrika Yolu", "Atölye Sokak"),
}

# How each language names a bank after a place. `{stem}` is the invented word.
BANK_NAMES: Mapping[str, str] = {
    "cs": "{stem} banka",
    "da": "{stem}banken",
    "de": "{stem}bank",
    "el": "Τράπεζα {stem}",
    "en": "{stem} Bank",
    "es": "Banco {stem}",
    "fi": "{stem}pankki",
    "fr": "Banque {stem}",
    "it": "Banca {stem}",
    "nl": "{stem}bank",
    "no": "{stem}banken",
    "pl": "Bank {stem}",
    "pt": "Banco {stem}",
    "sk": "{stem} banka",
    "sv": "{stem}banken",
    "tr": "{stem} Bankası",
}

# Where the house number goes. Only these two put it before the street name.
NUMBER_FIRST_LANGUAGES = frozenset({"en", "fr"})

LEGAL_FORMS: Mapping[str, tuple[str, ...]] = {
    "AT": ("GmbH", "AG", "OG"),
    "BE": ("BV", "NV", "SRL"),
    "CH": ("AG", "GmbH", "SA"),
    "CZ": ("s.r.o.", "a.s.", "v.o.s."),
    "DE": ("GmbH", "GmbH & Co. KG", "AG"),
    "DK": ("A/S", "ApS", "I/S"),
    "ES": ("S.L.", "S.A.", "S.L.U."),
    "FI": ("Oy", "Oyj", "Ky"),
    "FR": ("SARL", "SAS", "SA"),
    "GB": ("Ltd", "Limited", "PLC"),
    "GR": ("Α.Ε.", "Ε.Π.Ε.", "Ι.Κ.Ε."),
    "IE": ("Ltd", "Limited", "DAC"),
    "IT": ("S.r.l.", "S.p.A.", "S.a.s."),
    "LU": ("S.à r.l.", "SA", "SCS"),
    "NL": ("B.V.", "N.V.", "V.O.F."),
    "NO": ("AS", "ASA", "ANS"),
    "PL": ("Sp. z o.o.", "S.A.", "Sp.k."),
    "PT": ("Lda.", "S.A.", "Unipessoal Lda."),
    "SE": ("AB", "HB", "KB"),
    "SK": ("s.r.o.", "a.s.", "k.s."),
    "TR": ("A.Ş.", "Ltd. Şti.", "San. ve Tic. A.Ş."),
}

CITIES: Mapping[str, tuple[str, ...]] = {
    "AT": ("Linz", "Graz", "Salzburg", "Innsbruck", "Villach"),
    "BE": ("Gent", "Charleroi", "Leuven", "Namur", "Kortrijk"),
    "CH": ("Winterthur", "Biel", "Lugano", "Chur", "Olten"),
    "CZ": ("Brno", "Ostrava", "Plzeň", "Olomouc", "Liberec"),
    "DE": ("Duisburg", "Hamburg", "Leipzig", "Augsburg", "Kassel"),
    "DK": ("Aarhus", "Odense", "Aalborg", "Esbjerg", "Randers"),
    "ES": ("Valencia", "Zaragoza", "Bilbao", "Murcia", "Valladolid"),
    "FI": ("Tampere", "Turku", "Oulu", "Lahti", "Kuopio"),
    "FR": ("Lyon", "Nantes", "Strasbourg", "Rennes", "Toulouse"),
    "GB": ("Manchester", "Leeds", "Bristol", "Sheffield", "Coventry"),
    "GR": ("Θεσσαλονίκη", "Πάτρα", "Λάρισα", "Ηράκλειο", "Βόλος"),
    "IE": ("Cork", "Galway", "Limerick", "Waterford", "Drogheda"),
    "IT": ("Bologna", "Verona", "Padova", "Brescia", "Modena"),
    "LU": ("Differdange", "Dudelange", "Ettelbruck", "Diekirch", "Wiltz"),
    "NL": ("Eindhoven", "Groningen", "Tilburg", "Enschede", "Zwolle"),
    "NO": ("Bergen", "Trondheim", "Stavanger", "Drammen", "Kristiansand"),
    "PL": ("Poznań", "Wrocław", "Gdańsk", "Katowice", "Lublin"),
    "PT": ("Porto", "Braga", "Coimbra", "Aveiro", "Setúbal"),
    "SE": ("Göteborg", "Malmö", "Uppsala", "Norrköping", "Örebro"),
    "SK": ("Košice", "Žilina", "Nitra", "Prešov", "Trnava"),
    "TR": ("İzmir", "Bursa", "Adana", "Konya", "Gaziantep"),
}

POSTAL_CODES: Mapping[str, str] = {
    "AT": r"\d{4}",
    "BE": r"\d{4}",
    "CH": r"\d{4}",
    "CZ": r"\d{3} \d{2}",
    "DE": r"\d{5}",
    "DK": r"\d{4}",
    "ES": r"\d{5}",
    "FI": r"\d{5}",
    "FR": r"\d{5}",
    "GB": r"[A-Z]{2}\d \d[A-Z]{2}",
    "GR": r"\d{3} \d{2}",
    "IE": r"[A-Z]\d{2} [0-9A-Z]{4}",
    "IT": r"\d{5}",
    "LU": r"L-\d{4}",
    "NL": r"\d{4} [A-Z]{2}",
    "NO": r"\d{4}",
    "PL": r"\d{2}-\d{3}",
    "PT": r"\d{4}-\d{3}",
    "SE": r"\d{3} \d{2}",
    "SK": r"\d{3} \d{2}",
    "TR": r"\d{5}",
}

# What a country is called in the language its own invoices are written in. A document
# names no country but its own, so only the pairs a profile declares are ever read.
COUNTRY_NAMES: Mapping[str, Mapping[str, str]] = {
    "cs": {"CZ": "Česká republika"},
    "da": {"DK": "Danmark"},
    "de": {"DE": "Deutschland", "AT": "Österreich", "CH": "Schweiz"},
    "el": {"GR": "Ελλάδα"},
    "en": {"GB": "United Kingdom", "IE": "Ireland"},
    "es": {"ES": "España"},
    "fi": {"FI": "Suomi"},
    "fr": {"FR": "France", "BE": "Belgique", "LU": "Luxembourg"},
    "it": {"IT": "Italia"},
    "nl": {"NL": "Nederland", "BE": "België"},
    "no": {"NO": "Norge"},
    "pl": {"PL": "Polska"},
    "pt": {"PT": "Portugal"},
    "sk": {"SK": "Slovensko"},
    "sv": {"SE": "Sverige"},
    "tr": {"TR": "Türkiye"},
}
