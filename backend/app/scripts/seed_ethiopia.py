"""Seed a large, current Ethiopian knowledge graph into Atlas.

Covers all themed bundles plus major foreign influences:
  * Politics & government — PM/President, full cabinet, regional presidents,
    legislature, election board, security services
  * Parties & opposition — ruling Prosperity Party, TPLF (+ 2025 split), OLF/OLA,
    Fano, OFC, NaMA, EZEMA, ONLF
  * Conflict — Tigray war (+ Eritrean involvement, massacres), Amhara/Fano war,
    OLA insurgency, armed-group commanders
  * Economy & business — Ethiopian Investment Holdings + SOE portfolio, the
    2024–25 reforms (birr float, IMF programme, banking liberalization, ESX,
    Ethio Telecom IPO, BRICS accession), private banks, tycoons, conglomerates
  * Media & religion — state/private/diaspora outlets; the 2023 Orthodox schism
  * Foreign actors — Eritrea, Somalia/Somaliland, Djibouti, Egypt/Sudan (Nile),
    Turkey, UAE, Iran, China, USA (AGOA/sanctions), EU, World Bank/IMF, AU/IGAD,
    BRICS, Kenya/Safaricom

Compiled from public reporting (sources attached as evidence); **not**
authoritative — a starting graph for analysts to verify. Well-documented facts
get VERIFIED evidence; contested/allegation items get UNVERIFIED, feeding the
review workflow. Idempotent (dedupes by name+type, skips existing edges).

    DATABASE_URL=sqlite+aiosqlite:///./demo.db python -m app.scripts.seed_ethiopia
"""
from __future__ import annotations

import asyncio
import uuid

from sqlalchemy import select

from app.db.base import Base
from app.db.session import AsyncSessionLocal, engine
import app.models  # noqa: F401
from app.models.entity import Entity
from app.models.enums import (
    EntityType as ET,
    EvidenceStance,
    RelationshipType as RT,
    VerificationStatus,
)
from app.models.evidence import Evidence
from app.models.relationship import Relationship

P, O, C, G, L, E, A, D = (
    ET.PERSON, ET.ORGANIZATION, ET.COMPANY, ET.GOVERNMENT_AGENCY,
    ET.LOCATION, ET.EVENT, ET.ASSET, ET.DOCUMENT,
)

ENTITIES: dict[str, tuple] = {
    # ===================== LOCATIONS =====================
    "ethiopia": ("Ethiopia", L, {"country": "Ethiopia"}),
    "addis": ("Addis Ababa", L, {"country": "Ethiopia", "region": "Addis Ababa"}),
    "diredawa": ("Dire Dawa", L, {"country": "Ethiopia", "region": "Dire Dawa"}),
    # regions
    "tigray": ("Tigray Region", L, {"country": "Ethiopia", "region": "Tigray"}),
    "amhara": ("Amhara Region", L, {"country": "Ethiopia", "region": "Amhara"}),
    "oromia": ("Oromia Region", L, {"country": "Ethiopia", "region": "Oromia"}),
    "afar": ("Afar Region", L, {"country": "Ethiopia", "region": "Afar"}),
    "somali_reg": ("Somali Region", L, {"country": "Ethiopia", "region": "Somali"}),
    "sidama": ("Sidama Region", L, {"country": "Ethiopia", "region": "Sidama"}),
    "south_eth": ("South Ethiopia Region", L, {"country": "Ethiopia", "region": "South Ethiopia"}),
    "central_eth": ("Central Ethiopia Region", L, {"country": "Ethiopia", "region": "Central Ethiopia"}),
    "southwest": ("South West Ethiopia Region", L, {"country": "Ethiopia", "region": "South West"}),
    "benishangul": ("Benishangul-Gumuz Region", L, {"country": "Ethiopia", "region": "Benishangul-Gumuz"}),
    "gambela": ("Gambela Region", L, {"country": "Ethiopia", "region": "Gambela"}),
    "harari": ("Harari Region", L, {"country": "Ethiopia", "region": "Harari"}),
    # cities/towns
    "mekelle": ("Mekelle", L, {"country": "Ethiopia", "region": "Tigray"}),
    "axum": ("Axum", L, {"country": "Ethiopia", "region": "Tigray"}),
    "adigrat": ("Adigrat", L, {"country": "Ethiopia", "region": "Tigray"}),
    "shire": ("Shire", L, {"country": "Ethiopia", "region": "Tigray"}),
    "bahirdar": ("Bahir Dar", L, {"country": "Ethiopia", "region": "Amhara"}),
    "gondar": ("Gondar", L, {"country": "Ethiopia", "region": "Amhara"}),
    "dessie": ("Dessie", L, {"country": "Ethiopia", "region": "Amhara"}),
    "debark": ("Debark", L, {"country": "Ethiopia", "region": "Amhara"}),
    "metemma": ("Metemma", L, {"country": "Ethiopia", "region": "Amhara"}),
    "lalibela": ("Lalibela", L, {"country": "Ethiopia", "region": "Amhara"}),
    "adama": ("Adama", L, {"country": "Ethiopia", "region": "Oromia"}),
    "jimma": ("Jimma", L, {"country": "Ethiopia", "region": "Oromia"}),
    "nekemte": ("Nekemte", L, {"country": "Ethiopia", "region": "Oromia (Wollega)"}),
    "ambo": ("Ambo", L, {"country": "Ethiopia", "region": "Oromia"}),
    "hawassa": ("Hawassa", L, {"country": "Ethiopia", "region": "Sidama"}),
    "jijiga": ("Jijiga", L, {"country": "Ethiopia", "region": "Somali"}),
    "semera": ("Semera", L, {"country": "Ethiopia", "region": "Afar"}),
    "assosa": ("Assosa", L, {"country": "Ethiopia", "region": "Benishangul-Gumuz"}),
    "guba": ("Guba (GERD site)", L, {"country": "Ethiopia", "region": "Benishangul-Gumuz"}),
    # geography
    "blue_nile": ("Blue Nile (Abbay) River", L, {"country": "Ethiopia"}),
    "red_sea": ("Red Sea", L, {"country": "International waters"}),
    # foreign countries
    "eritrea": ("Eritrea", L, {"country": "Eritrea"}),
    "asmara": ("Asmara", L, {"country": "Eritrea"}),
    "assab": ("Assab", L, {"country": "Eritrea", "region": "Southern Red Sea"}),
    "somalia": ("Somalia", L, {"country": "Somalia"}),
    "mogadishu": ("Mogadishu", L, {"country": "Somalia"}),
    "somaliland": ("Somaliland", L, {"country": "Somaliland (self-declared)"}),
    "berbera": ("Berbera", L, {"country": "Somaliland", "region": "Sahil"}),
    "djibouti": ("Djibouti", L, {"country": "Djibouti"}),
    "sudan": ("Sudan", L, {"country": "Sudan"}),
    "south_sudan": ("South Sudan", L, {"country": "South Sudan"}),
    "kenya": ("Kenya", L, {"country": "Kenya"}),
    "egypt": ("Egypt", L, {"country": "Egypt"}),
    "turkey": ("Turkey", L, {"country": "Turkey"}),
    "uae": ("United Arab Emirates", L, {"country": "United Arab Emirates"}),
    "iran": ("Iran", L, {"country": "Iran"}),
    "china": ("China", L, {"country": "China"}),
    "usa": ("United States", L, {"country": "United States"}),
    "russia": ("Russia", L, {"country": "Russia"}),
    "saudi": ("Saudi Arabia", L, {"country": "Saudi Arabia"}),
    "sweden": ("Sweden", L, {"country": "Sweden"}),

    # ===================== PEOPLE: federal government =====================
    "abiy": ("Abiy Ahmed", P, {"occupation": "Prime Minister of Ethiopia", "nationality": "Ethiopian"}),
    "taye": ("Taye Atske Selassie", P, {"occupation": "President of Ethiopia", "nationality": "Ethiopian"}),
    "sahlework": ("Sahle-Work Zewde", P, {"occupation": "Former President of Ethiopia", "nationality": "Ethiopian"}),
    "temesgen_t": ("Temesgen Tiruneh", P, {"occupation": "Deputy PM; ex-NISS Director", "nationality": "Ethiopian"}),
    "ahmed_shide": ("Ahmed Shide", P, {"occupation": "Minister of Finance", "nationality": "Ethiopian"}),
    "gedion_t": ("Gedion Timothewos", P, {"occupation": "Minister of Foreign Affairs", "nationality": "Ethiopian"}),
    "aisha": ("Aisha Mohammed Mussa", P, {"occupation": "Minister of Defense", "nationality": "Ethiopian"}),
    "mohamed_idris": ("Mohamed Idris", P, {"occupation": "Minister of Peace", "nationality": "Ethiopian"}),
    "berhanu_nega": ("Berhanu Nega", P, {"occupation": "Minister of Education; EZEMA leader", "nationality": "Ethiopian"}),
    "mekdes_daba": ("Mekdes Daba", P, {"occupation": "Minister of Health", "nationality": "Ethiopian"}),
    "melaku_alebel": ("Melaku Alebel", P, {"occupation": "Minister of Industry", "nationality": "Ethiopian"}),
    "belete_molla": ("Belete Molla", P, {"occupation": "Minister of Innovation and Technology", "nationality": "Ethiopian"}),
    "girma_amente": ("Girma Amente", P, {"occupation": "Minister of Agriculture", "nationality": "Ethiopian"}),
    "fitsum_assefa": ("Fitsum Assefa", P, {"occupation": "Minister of Planning and Development", "nationality": "Ethiopian"}),
    "shewit_shanka": ("Shewit Shanka", P, {"occupation": "Minister of Culture and Sport", "nationality": "Ethiopian"}),
    "eyob": ("Eyob Tekalign", P, {"occupation": "Governor, National Bank of Ethiopia", "nationality": "Ethiopian"}),
    "mamo": ("Mamo Mihretu", P, {"occupation": "CEO, Ethiopian Investment Holdings; ex-NBE Governor", "nationality": "Ethiopian"}),
    "berhanu_adelo": ("Berhanu Adelo", P, {"occupation": "Chief Commissioner, EHRC", "nationality": "Ethiopian"}),
    "demeke": ("Demeke Mekonnen", P, {"occupation": "Former Deputy PM and Foreign Minister", "nationality": "Ethiopian"}),
    "birhanu_jula": ("Birhanu Jula", P, {"occupation": "Chief of General Staff, ENDF (Field Marshal)", "nationality": "Ethiopian"}),
    "abebaw_tadesse": ("Abebaw Tadesse", P, {"occupation": "Deputy Chief of Staff, ENDF", "nationality": "Ethiopian"}),
    "lemma": ("Lemma Megersa", P, {"occupation": "Former Minister of Defense", "nationality": "Ethiopian"}),
    "adanech": ("Adanech Abebe", P, {"occupation": "Mayor of Addis Ababa", "nationality": "Ethiopian"}),
    "tagesse": ("Tagesse Chafo", P, {"occupation": "Speaker, House of Peoples' Representatives", "nationality": "Ethiopian"}),

    # ===================== PEOPLE: regional presidents =====================
    "shimelis": ("Shimelis Abdisa", P, {"occupation": "President of Oromia Region", "nationality": "Ethiopian"}),
    "arega_kebede": ("Arega Kebede", P, {"occupation": "President of Amhara Region", "nationality": "Ethiopian"}),
    "awol_arba": ("Awol Arba", P, {"occupation": "President of Afar Region", "nationality": "Ethiopian"}),
    "mustafa_omar": ("Mustafa Mohammed Omar", P, {"occupation": "President of Somali Region", "nationality": "Ethiopian"}),
    "desta_ledamo": ("Desta Ledamo", P, {"occupation": "President of Sidama Region", "nationality": "Ethiopian"}),
    "tilahun_kebede": ("Tilahun Kebede", P, {"occupation": "Chief Administrator, South Ethiopia Region", "nationality": "Ethiopian"}),
    "endashaw_t": ("Endashaw Tassew", P, {"occupation": "Chief Administrator, Central Ethiopia Region", "nationality": "Ethiopian"}),

    # ===================== PEOPLE: Tigray / opposition / activists =====================
    "debretsion": ("Debretsion Gebremichael", P, {"occupation": "Chairman, TPLF", "nationality": "Ethiopian"}),
    "getachew": ("Getachew Reda", P, {"occupation": "Federal adviser; ex-President, Tigray Interim Administration", "nationality": "Ethiopian"}),
    "tadesse_w": ("Tadesse Werede", P, {"occupation": "President of Tigray Interim Administration; TDF commander", "nationality": "Ethiopian"}),
    "jawar": ("Jawar Mohammed", P, {"occupation": "Politician; founder of OMN", "nationality": "Ethiopian"}),
    "merera": ("Merera Gudina", P, {"occupation": "Chairman, Oromo Federalist Congress", "nationality": "Ethiopian"}),
    "bekele_gerba": ("Bekele Gerba", P, {"occupation": "Opposition politician (OFC)", "nationality": "Ethiopian"}),
    "eskinder": ("Eskinder Nega", P, {"occupation": "Journalist and politician (Balderas)", "nationality": "Ethiopian"}),
    "lidetu": ("Lidetu Ayalew", P, {"occupation": "Veteran opposition politician", "nationality": "Ethiopian"}),

    # ===================== PEOPLE: armed-group commanders =====================
    "jaal_marroo": ("Kumsa Diriba (Jaal Marroo)", P, {"occupation": "Commander-in-Chief, Oromo Liberation Army", "nationality": "Ethiopian"}),
    "zemene_kassie": ("Zemene Kassie", P, {"occupation": "Fano commander (Amhara)", "nationality": "Ethiopian"}),
    "eskinder_fano": ("Habte Wolde", P, {"occupation": "Fano figure (Amhara)", "nationality": "Ethiopian"}),

    # ===================== PEOPLE: religion =====================
    "abune_mathias": ("Abune Mathias", P, {"occupation": "Patriarch, Ethiopian Orthodox Tewahedo Church", "nationality": "Ethiopian"}),
    "abune_sawiros": ("Abune Sawiros", P, {"occupation": "Leader of the 2023 breakaway synod", "nationality": "Ethiopian"}),

    # ===================== PEOPLE: business =====================
    "al_amoudi": ("Mohammed Hussein Al Amoudi", P, {"occupation": "Billionaire; founder of MIDROC", "nationality": "Ethiopian-Saudi"}),
    "belayneh_k": ("Belayneh Kindie", P, {"occupation": "Businessman; founder of Belayneh Kindie Group", "nationality": "Ethiopian"}),
    "buzuayehu": ("Buzuayehu Tadele Bizenu", P, {"occupation": "Founder, East African Holding", "nationality": "Ethiopian"}),
    "samuel_tafesse": ("Samuel Tafesse", P, {"occupation": "Founder, Sunshine Investment Group", "nationality": "Ethiopian"}),

    # ===================== PEOPLE: foreign =====================
    "isaias": ("Isaias Afwerki", P, {"occupation": "President of Eritrea", "nationality": "Eritrean"}),
    "hassan_smm": ("Hassan Sheikh Mohamud", P, {"occupation": "President of Somalia", "nationality": "Somali"}),
    "irro": ("Abdirahman Mohamed Abdullahi (Irro)", P, {"occupation": "President of Somaliland", "nationality": "Somalilander"}),
    "muse_bihi": ("Muse Bihi Abdi", P, {"occupation": "Former President of Somaliland", "nationality": "Somalilander"}),
    "erdogan": ("Recep Tayyip Erdoğan", P, {"occupation": "President of Turkey", "nationality": "Turkish"}),
    "mbz": ("Mohamed bin Zayed Al Nahyan", P, {"occupation": "President of the UAE", "nationality": "Emirati"}),
    "sisi": ("Abdel Fattah el-Sisi", P, {"occupation": "President of Egypt", "nationality": "Egyptian"}),
    "ruto": ("William Ruto", P, {"occupation": "President of Kenya", "nationality": "Kenyan"}),
    "guelleh": ("Ismaïl Omar Guelleh", P, {"occupation": "President of Djibouti", "nationality": "Djiboutian"}),
    "burhan": ("Abdel Fattah al-Burhan", P, {"occupation": "Leader of Sudan's Sovereignty Council", "nationality": "Sudanese"}),
    "xi": ("Xi Jinping", P, {"occupation": "President of China", "nationality": "Chinese"}),
    "trump": ("Donald Trump", P, {"occupation": "President of the United States", "nationality": "American"}),
    "obasanjo": ("Olusegun Obasanjo", P, {"occupation": "AU High Representative for the Horn of Africa", "nationality": "Nigerian"}),
    "moussa_faki": ("Moussa Faki Mahamat", P, {"occupation": "Former Chairperson, AU Commission", "nationality": "Chadian"}),
    "mike_hammer": ("Mike Hammer", P, {"occupation": "Former US Special Envoy for the Horn of Africa", "nationality": "American"}),
    "annette_weber": ("Annette Weber", P, {"occupation": "Former EU Special Envoy for the Horn of Africa", "nationality": "German"}),

    # ===================== PARTIES & ORGANIZATIONS =====================
    "pp": ("Prosperity Party", O, {"org_type": "Ruling political party", "founded_date": "2019-12-01"}),
    "tplf": ("Tigray People's Liberation Front", O, {"org_type": "Political party / former ruling front"}),
    "olf": ("Oromo Liberation Front", O, {"org_type": "Political party"}),
    "ola": ("Oromo Liberation Army", O, {"org_type": "Armed group (OLF-Shene)"}),
    "ofc": ("Oromo Federalist Congress", O, {"org_type": "Opposition party"}),
    "nama": ("National Movement of Amhara", O, {"org_type": "Opposition party"}),
    "ezema": ("Ethiopian Citizens for Social Justice (EZEMA)", O, {"org_type": "Opposition party"}),
    "balderas": ("Balderas for True Democracy", O, {"org_type": "Opposition party"}),
    "fano": ("Fano", O, {"org_type": "Amhara nationalist militia movement"}),
    "onlf": ("Ogaden National Liberation Front", O, {"org_type": "Former armed group / party"}),
    "tia": ("Tigray Interim Administration", O, {"org_type": "Regional interim government"}),
    "effort": ("EFFORT (Endowment Fund for the Rehabilitation of Tigray)", O, {"org_type": "Party-affiliated business conglomerate"}),
    "pfdj": ("PFDJ (Eritrea ruling party)", O, {"org_type": "Eritrea ruling party"}),
    "eotc": ("Ethiopian Orthodox Tewahedo Church", O, {"org_type": "Religious institution"}),
    "oromia_synod": ("Breakaway Oromia/Southern Synod (2023)", O, {"org_type": "Breakaway religious synod"}),
    "mejlis": ("Ethiopian Islamic Affairs Supreme Council", O, {"org_type": "Religious institution"}),
    # international
    "au": ("African Union", O, {"org_type": "Continental organization", "headquarters": "Addis Ababa"}),
    "igad": ("IGAD", O, {"org_type": "Regional bloc (Horn of Africa)", "headquarters": "Djibouti"}),
    "un": ("United Nations", O, {"org_type": "International organization"}),
    "brics": ("BRICS", O, {"org_type": "Intergovernmental bloc"}),
    "worldbank": ("World Bank", O, {"org_type": "International financial institution"}),
    "imf": ("International Monetary Fund", O, {"org_type": "International financial institution"}),
    "eu": ("European Union", O, {"org_type": "Supranational union"}),
    # media
    "ebc": ("Ethiopian Broadcasting Corporation (EBC)", O, {"org_type": "State broadcaster"}),
    "fana_bc": ("Fana Broadcasting Corporate", O, {"org_type": "State-affiliated broadcaster"}),
    "walta": ("Walta Media", O, {"org_type": "State-affiliated media"}),
    "esat": ("ESAT (Ethiopian Satellite Television)", O, {"org_type": "Diaspora broadcaster"}),
    "omn": ("Oromia Media Network (OMN)", O, {"org_type": "Media network"}),
    "addis_standard": ("Addis Standard", O, {"org_type": "Independent media"}),
    "ethiopia_insight": ("Ethiopia Insight", O, {"org_type": "Independent analysis media"}),
    "tigrai_tv": ("Tigrai TV", O, {"org_type": "Regional broadcaster"}),

    # ===================== GOVERNMENT AGENCIES / SECURITY =====================
    "pmo": ("Office of the Prime Minister of Ethiopia", G, {"jurisdiction": "Federal"}),
    "hopr": ("House of Peoples' Representatives", G, {"jurisdiction": "Federal legislature"}),
    "hof": ("House of Federation", G, {"jurisdiction": "Federal upper house"}),
    "nebe": ("National Election Board of Ethiopia", G, {"jurisdiction": "Federal"}),
    "mfa": ("Ministry of Foreign Affairs (Ethiopia)", G, {"jurisdiction": "Federal"}),
    "mod": ("Ministry of Defense (Ethiopia)", G, {"jurisdiction": "Federal"}),
    "mofin": ("Ministry of Finance (Ethiopia)", G, {"jurisdiction": "Federal"}),
    "moh": ("Ministry of Health (Ethiopia)", G, {"jurisdiction": "Federal"}),
    "moe": ("Ministry of Education (Ethiopia)", G, {"jurisdiction": "Federal"}),
    "moa": ("Ministry of Agriculture (Ethiopia)", G, {"jurisdiction": "Federal"}),
    "mopeace": ("Ministry of Peace (Ethiopia)", G, {"jurisdiction": "Federal"}),
    "nbe": ("National Bank of Ethiopia", G, {"jurisdiction": "Federal central bank"}),
    "ecma": ("Ethiopian Capital Market Authority", G, {"jurisdiction": "Federal regulator"}),
    "niss": ("National Intelligence and Security Service", G, {"jurisdiction": "Federal"}),
    "ehrc": ("Ethiopian Human Rights Commission", G, {"jurisdiction": "Federal"}),
    "fed_police": ("Ethiopian Federal Police", G, {"jurisdiction": "Federal"}),
    "endf": ("Ethiopian National Defence Force", G, {"jurisdiction": "Federal armed forces"}),
    "edf": ("Eritrean Defence Forces", G, {"jurisdiction": "Eritrea armed forces"}),
    "tdf": ("Tigray Defense Forces", G, {"jurisdiction": "Tigray regional armed force"}),
    "amhara_sf": ("Amhara Special Forces (disbanded 2023)", G, {"jurisdiction": "Amhara regional force"}),

    # ===================== COMPANIES / STATE & PRIVATE =====================
    "eih": ("Ethiopian Investment Holdings", C, {"industry": "Sovereign wealth fund"}),
    "ethio_air": ("Ethiopian Airlines", C, {"industry": "Aviation"}),
    "cbe": ("Commercial Bank of Ethiopia", C, {"industry": "Banking"}),
    "ethio_tel": ("Ethio Telecom", C, {"industry": "Telecommunications"}),
    "eep": ("Ethiopian Electric Power", C, {"industry": "Electric power"}),
    "erc": ("Ethiopian Railway Corporation", C, {"industry": "Rail transport"}),
    "dbe": ("Development Bank of Ethiopia", C, {"industry": "Development banking"}),
    "ipdc": ("Industrial Parks Development Corporation", C, {"industry": "Industrial parks"}),
    "esl": ("Ethiopian Shipping & Logistics", C, {"industry": "Shipping and logistics"}),
    "metec": ("Metals and Engineering Corporation (METEC)", C, {"industry": "Military-industrial"}),
    "esx": ("Ethiopian Securities Exchange (ESX)", C, {"industry": "Securities exchange"}),
    # private banks
    "awash_bank": ("Awash Bank", C, {"industry": "Banking"}),
    "dashen_bank": ("Dashen Bank", C, {"industry": "Banking"}),
    "abyssinia_bank": ("Bank of Abyssinia", C, {"industry": "Banking"}),
    "coop_oromia": ("Cooperative Bank of Oromia", C, {"industry": "Banking"}),
    "zemen_bank": ("Zemen Bank", C, {"industry": "Banking"}),
    "wegagen_bank": ("Wegagen Bank", C, {"industry": "Banking"}),
    # conglomerates / private
    "midroc": ("MIDROC Ethiopia", C, {"industry": "Diversified conglomerate"}),
    "midroc_gold": ("MIDROC Gold (Lega Dembi)", C, {"industry": "Mining"}),
    "derba": ("Derba Cement", C, {"industry": "Cement"}),
    "noc": ("National Oil Company (NOC)", C, {"industry": "Fuel distribution"}),
    "bkg": ("Belayneh Kindie Group", C, {"industry": "Agriculture and trading"}),
    "eahsc": ("East African Holding", C, {"industry": "Diversified manufacturing"}),
    "sunshine": ("Sunshine Investment Group", C, {"industry": "Construction and real estate"}),
    "bgi": ("BGI Ethiopia", C, {"industry": "Brewing"}),
    "preem": ("Preem", C, {"industry": "Oil refining (Sweden)"}),
    # telecom consortium
    "safaricom_et": ("Safaricom Telecommunications Ethiopia", C, {"industry": "Telecommunications"}),
    "safaricom": ("Safaricom", C, {"industry": "Telecommunications"}),
    "vodacom": ("Vodacom Group", C, {"industry": "Telecommunications"}),
    # EFFORT subsidiaries
    "mesfin": ("Mesfin Industrial Engineering", C, {"industry": "Engineering"}),
    "guna": ("Guna Trading House", C, {"industry": "Trading"}),

    # ===================== ASSETS =====================
    "gerd": ("Grand Ethiopian Renaissance Dam (GERD)", A, {"asset_type": "Hydroelectric dam"}),
    "addis_djibouti_rail": ("Addis Ababa–Djibouti Railway", A, {"asset_type": "Railway infrastructure"}),
    "bayraktar": ("Bayraktar TB2 drones", A, {"asset_type": "Combat UAV (Turkey)"}),
    "wing_loong": ("Wing Loong drones", A, {"asset_type": "Combat UAV (China)"}),
    "mohajer6": ("Mohajer-6 drones", A, {"asset_type": "Combat UAV (Iran)"}),

    # ===================== EVENTS =====================
    "ev_reform18": ("Abiy Ahmed reforms begin", E, {"date": "2018-04-02", "location": "Ethiopia"}),
    "ev_eth_eri_peace": ("Ethiopia–Eritrea peace agreement", E, {"date": "2018-07-09", "location": "Asmara"}),
    "ev_nobel": ("2019 Nobel Peace Prize (Abiy Ahmed)", E, {"date": "2019-12-10", "location": "Oslo"}),
    "ev_sidama_ref": ("2019 Sidama statehood referendum", E, {"date": "2019-11-20", "location": "Sidama"}),
    "ev_tigray_war": ("Tigray War (2020–2022)", E, {"date": "2020-11-03", "location": "Tigray"}),
    "ev_mai_kadra": ("Mai Kadra massacre", E, {"date": "2020-11-09", "location": "Mai Kadra, Tigray"}),
    "ev_agoa_susp": ("Ethiopia suspended from AGOA", E, {"date": "2022-01-01", "location": "United States"}),
    "ev_election21": ("2021 Ethiopian general election", E, {"date": "2021-06-21", "location": "Ethiopia"}),
    "ev_pretoria": ("Pretoria Agreement (Cessation of Hostilities)", E, {"date": "2022-11-02", "location": "Pretoria"}),
    "ev_orthodox": ("2023 Ethiopian Orthodox Church schism", E, {"date": "2023-01-22", "location": "Oromia"}),
    "ev_amhara_war": ("Amhara (Fano) conflict", E, {"date": "2023-08-01", "location": "Amhara"}),
    "ev_brics": ("Ethiopia joins BRICS", E, {"date": "2024-01-01", "location": "Ethiopia"}),
    "ev_somaliland_mou": ("Ethiopia–Somaliland Memorandum of Understanding", E, {"date": "2024-01-01", "location": "Addis Ababa"}),
    "ev_birr_float": ("Ethiopia floats the birr (IMF programme)", E, {"date": "2024-07-29", "location": "Ethiopia"}),
    "ev_banking_lib": ("Banking sector opened to foreign banks", E, {"date": "2024-12-17", "location": "Ethiopia"}),
    "ev_ankara": ("Ankara Declaration (Ethiopia–Somalia)", E, {"date": "2024-12-12", "location": "Ankara"}),
    "ev_esx_launch": ("Ethiopian Securities Exchange launches", E, {"date": "2025-01-10", "location": "Addis Ababa"}),
    "ev_tplf_split": ("TPLF factional split / Tigray leadership change", E, {"date": "2025-03-01", "location": "Mekelle"}),
    "ev_gerd_inaug": ("GERD inauguration", E, {"date": "2025-09-09", "location": "Guba"}),
    "ev_ethiotel_ipo": ("Ethio Telecom IPO and ESX listing", E, {"date": "2025-04-01", "location": "Addis Ababa"}),
    "ev_eritrea_crisis": ("Ethiopia–Eritrea war-risk crisis (2025–26)", E, {"date": "2025-11-01", "location": "Tigray border"}),
    "ev_debt_deal": ("IMF/World Bank debt restructuring programme", E, {"date": "2024-07-01", "location": "Addis Ababa"}),

    # ===================== DOCUMENTS =====================
    "doc_pretoria": ("Cessation of Hostilities Agreement (text)", D, {"doc_type": "Treaty", "source": "African Union", "publication_date": "2022-11-02"}),
    "doc_eo14046": ("US Executive Order 14046 (northern Ethiopia)", D, {"doc_type": "Executive order", "source": "The White House", "publication_date": "2021-09-17"}),
    "doc_imf_report": ("IMF Country Report on Ethiopia (2025)", D, {"doc_type": "IMF report", "source": "International Monetary Fund"}),
    "doc_icg_powderkeg": ("ICG: Ethiopia, Eritrea and Tigray — A Powder Keg", D, {"doc_type": "Analysis report", "source": "International Crisis Group"}),
    "doc_ecfr_drones": ("ECFR: Deadly skies — Drone warfare in Ethiopia", D, {"doc_type": "Research report", "source": "European Council on Foreign Relations"}),
}

WIKI = "https://en.wikipedia.org/wiki/"


def ev(title, source, url, verified=True, stance=EvidenceStance.SUPPORTS):
    return (title, source, url, verified, stance)


RELS: list[tuple] = [
    # ===================== Geography backbone =====================
    *[(r, RT.LOCATED_IN, "ethiopia", 0.95, None) for r in
      ["tigray", "amhara", "oromia", "afar", "somali_reg", "sidama", "south_eth",
       "central_eth", "southwest", "benishangul", "gambela", "harari", "addis", "diredawa"]],
    *[(c, RT.LOCATED_IN, "tigray", 0.9, None) for c in ["mekelle", "axum", "adigrat", "shire"]],
    *[(c, RT.LOCATED_IN, "amhara", 0.9, None) for c in ["bahirdar", "gondar", "dessie", "debark", "metemma", "lalibela"]],
    *[(c, RT.LOCATED_IN, "oromia", 0.9, None) for c in ["adama", "jimma", "nekemte", "ambo"]],
    ("hawassa", RT.LOCATED_IN, "sidama", 0.9, None),
    ("jijiga", RT.LOCATED_IN, "somali_reg", 0.9, None),
    ("semera", RT.LOCATED_IN, "afar", 0.9, None),
    ("assosa", RT.LOCATED_IN, "benishangul", 0.9, None),
    ("guba", RT.LOCATED_IN, "benishangul", 0.9, None),
    ("blue_nile", RT.LOCATED_IN, "ethiopia", 0.9, None),
    ("asmara", RT.LOCATED_IN, "eritrea", 0.95, None),
    ("assab", RT.LOCATED_IN, "eritrea", 0.95, None),
    ("mogadishu", RT.LOCATED_IN, "somalia", 0.9, None),
    ("berbera", RT.LOCATED_IN, "somaliland", 0.9, None),
    ("somaliland", RT.CONNECTED_TO, "somalia", 0.8,
     ev("Somaliland is internationally recognised as part of Somalia", "Wikipedia", WIKI + "Somaliland")),
    ("au", RT.LOCATED_IN, "addis", 0.95, None),
    ("blue_nile", RT.CONNECTED_TO, "gerd", 0.9, None),
    ("blue_nile", RT.CONNECTED_TO, "egypt", 0.7, None),

    # ===================== Federal government: PM, President, cabinet =====================
    ("abiy", RT.MANAGES, "pmo", 0.95,
     ev("Abiy Ahmed is Prime Minister of Ethiopia since 2018", "Britannica", "https://www.britannica.com/biography/Abiy-Ahmed")),
    ("abiy", RT.MEMBER_OF, "pp", 0.95, None),
    ("abiy", RT.FOUNDED, "pp", 0.9,
     ev("Abiy formed the Prosperity Party from the EPRDF in 2019", "Wikipedia", WIKI + "Prosperity_Party")),
    ("abiy", RT.MANAGES, "endf", 0.8, None),
    ("abiy", RT.PARTICIPATED_IN, "ev_reform18", 0.9, None),
    ("taye", RT.MANAGES, "ethiopia", 0.7,
     ev("Taye Atske Selassie became President on 7 October 2024", "Wikipedia", WIKI + "Taye_Atske_Selassie")),
    ("taye", RT.MEMBER_OF, "pp", 0.7, None),
    ("sahlework", RT.ASSOCIATED_WITH, "ethiopia", 0.6,
     ev("Sahle-Work Zewde served as President until October 2024", "Wikipedia", WIKI + "Sahle-Work_Zewde")),
    ("temesgen_t", RT.MANAGES, "niss", 0.7, None),
    ("temesgen_t", RT.WORKS_FOR, "pmo", 0.7, None),
    ("ahmed_shide", RT.MANAGES, "mofin", 0.85,
     ev("Ahmed Shide is Minister of Finance since 2018", "Wikipedia", WIKI + "Ahmed_Shide")),
    ("gedion_t", RT.MANAGES, "mfa", 0.85,
     ev("Gedion Timothewos became Foreign Minister in October 2024", "Wikipedia", WIKI + "Gedion_Timothewos")),
    ("aisha", RT.MANAGES, "mod", 0.85,
     ev("Aisha Mohammed Mussa is Minister of Defense since May 2024", "Wikipedia", WIKI + "Aisha_Mohammed_(politician)")),
    ("mohamed_idris", RT.MANAGES, "mopeace", 0.7,
     ev("Mohamed Idris appointed Minister of Peace, November 2024", "Wikipedia", WIKI + "Mohamed_Idris_(Ethiopian_politician)")),
    ("berhanu_nega", RT.MANAGES, "moe", 0.8, None),
    ("mekdes_daba", RT.MANAGES, "moh", 0.75, None),
    ("girma_amente", RT.MANAGES, "moa", 0.7, None),
    ("eyob", RT.MANAGES, "nbe", 0.85,
     ev("Eyob Tekalign appointed NBE Governor, September 2025", "Wikipedia", WIKI + "Eyob_Tekalign")),
    ("mamo", RT.MANAGES, "eih", 0.8, None),
    ("berhanu_adelo", RT.MANAGES, "ehrc", 0.7,
     ev("Berhanu Adelo became EHRC Chief Commissioner, January 2025", "Wikipedia", WIKI + "Berhanu_Adelo")),
    ("birhanu_jula", RT.MANAGES, "endf", 0.85, None),
    ("abebaw_tadesse", RT.WORKS_FOR, "endf", 0.7, None),
    ("tagesse", RT.MANAGES, "hopr", 0.7, None),
    ("adanech", RT.MANAGES, "addis", 0.8, None),
    # cabinet members of Prosperity Party
    *[(m, RT.MEMBER_OF, "pp", 0.7, None) for m in
      ["taye", "ahmed_shide", "gedion_t", "aisha", "mekdes_daba", "melaku_alebel",
       "belete_molla", "girma_amente", "fitsum_assefa", "shewit_shanka", "adanech",
       "temesgen_t", "demeke", "mohamed_idris"]],
    *[(m, RT.WORKS_FOR, "pmo", 0.6, None) for m in
      ["ahmed_shide", "gedion_t", "aisha", "mohamed_idris", "berhanu_nega",
       "mekdes_daba", "melaku_alebel", "belete_molla", "girma_amente", "fitsum_assefa"]],
    ("melaku_alebel", RT.WORKS_FOR, "pmo", 0.6, None),
    ("pp", RT.CONNECTED_TO, "hopr", 0.85,
     ev("Prosperity Party holds the overwhelming majority in parliament", "Wikipedia", WIKI + "Prosperity_Party")),
    ("pp", RT.PARTICIPATED_IN, "ev_election21", 0.85,
     ev("Prosperity Party won the 2021 general election", "Wikipedia", WIKI + "2021_Ethiopian_general_election")),
    ("nebe", RT.SUPERVISES, "ev_election21", 0.8, None),
    ("hof", RT.CONNECTED_TO, "ethiopia", 0.6, None),

    # ===================== Regional presidents =====================
    ("shimelis", RT.MANAGES, "oromia", 0.85,
     ev("Shimelis Abdisa is President of Oromia Region since 2019", "Wikipedia", WIKI + "Shimelis_Abdisa")),
    ("arega_kebede", RT.MANAGES, "amhara", 0.8,
     ev("Arega Kebede became President of Amhara Region in August 2023", "Wikipedia", WIKI + "Arega_Kebede")),
    ("awol_arba", RT.MANAGES, "afar", 0.8, None),
    ("mustafa_omar", RT.MANAGES, "somali_reg", 0.8, None),
    ("desta_ledamo", RT.MANAGES, "sidama", 0.75, None),
    ("tilahun_kebede", RT.MANAGES, "south_eth", 0.7, None),
    ("endashaw_t", RT.MANAGES, "central_eth", 0.7, None),
    ("tadesse_w", RT.MANAGES, "tigray", 0.7, None),
    *[(p, RT.MEMBER_OF, "pp", 0.7, None) for p in
      ["shimelis", "arega_kebede", "awol_arba", "mustafa_omar", "desta_ledamo",
       "tilahun_kebede", "endashaw_t"]],
    ("ev_sidama_ref", RT.CONNECTED_TO, "sidama", 0.8,
     ev("Sidama voted for its own regional statehood in the 2019 referendum", "Wikipedia", WIKI + "Sidama_Region")),

    # ===================== Parties / opposition =====================
    ("debretsion", RT.MANAGES, "tplf", 0.85, None),
    ("debretsion", RT.MEMBER_OF, "tplf", 0.9, None),
    ("getachew", RT.MEMBER_OF, "tplf", 0.7, None),
    ("getachew", RT.ASSOCIATED_WITH, "tia", 0.7,
     ev("Getachew Reda led the Tigray Interim Administration until March 2025", "Addis Standard",
        "https://addisstandard.com/divided-and-disputed-tplfs-fractured-leadership-electoral-board-feud-threaten-tigrays-fragile-peace/")),
    ("getachew", RT.WORKS_FOR, "pmo", 0.6,
     ev("Getachew joined the federal government as an adviser after the 2025 split", "Borkena",
        "https://borkena.com/2025/04/29/ethiopia-getachew-reda-pm-advisor-and-tplf-figure-moves-to-form-new-political-party-amidst-registration-dispute/", False)),
    ("tadesse_w", RT.MANAGES, "tia", 0.7,
     ev("Tadesse Werede replaced Getachew Reda as head of the TIA in March 2025", "ACLED",
        "https://acleddata.com/update/ethiopia-situation-update-19-march-2025", False)),
    ("tadesse_w", RT.MANAGES, "tdf", 0.7, None),
    ("debretsion", RT.CONNECTED_TO, "getachew", 0.6,
     ev("TPLF split into Debretsion and Getachew factions in 2025", "Wikipedia", WIKI + "TPLF_factional_dispute", False)),
    ("ev_tplf_split", RT.CONNECTED_TO, "tplf", 0.8, None),
    ("ev_tplf_split", RT.LOCATED_IN, "tigray", 0.8, None),
    ("tplf", RT.OWNS, "effort", 0.7,
     ev("EFFORT is the TPLF's business conglomerate", "Wikipedia", WIKI + "Endowment_Fund_for_the_Rehabilitation_of_Tigray")),
    ("effort", RT.OWNS, "mesfin", 0.7, None),
    ("effort", RT.OWNS, "guna", 0.7, None),
    ("merera", RT.MANAGES, "ofc", 0.75, None),
    ("merera", RT.MEMBER_OF, "ofc", 0.8, None),
    ("jawar", RT.MEMBER_OF, "ofc", 0.7, None),
    ("jawar", RT.FOUNDED, "omn", 0.8,
     ev("Jawar Mohammed founded the Oromia Media Network", "Wikipedia", WIKI + "Jawar_Mohammed")),
    ("bekele_gerba", RT.MEMBER_OF, "ofc", 0.7, None),
    ("berhanu_nega", RT.MANAGES, "ezema", 0.8, None),
    ("berhanu_nega", RT.FOUNDED, "ezema", 0.6, None),
    ("eskinder", RT.MANAGES, "balderas", 0.7, None),
    ("eskinder", RT.FOUNDED, "balderas", 0.6, None),
    ("ola", RT.ASSOCIATED_WITH, "olf", 0.7,
     ev("The OLA split from the OLF in 2018", "Wikipedia", WIKI + "Oromo_Liberation_Army")),
    ("onlf", RT.ASSOCIATED_WITH, "somali_reg", 0.6, None),

    # ===================== Armed groups & conflicts =====================
    ("jaal_marroo", RT.MANAGES, "ola", 0.8,
     ev("Kumsa Diriba (Jaal Marroo) is commander-in-chief of the OLA", "Jamestown Foundation",
        "https://jamestown.org/a-profile-of-jaal-marroo-the-leader-of-ethiopias-oromo-liberation-army/")),
    ("ola", RT.PARTICIPATED_IN, "ev_amhara_war", 0.4, None),
    ("ola", RT.LOCATED_IN, "oromia", 0.8, None),
    ("zemene_kassie", RT.ASSOCIATED_WITH, "fano", 0.7,
     ev("Zemene Kassie is a prominent Fano commander", "Wikipedia", WIKI + "Fano_(militia)")),
    ("eskinder_fano", RT.ASSOCIATED_WITH, "fano", 0.4, None),
    ("eskinder", RT.ASSOCIATED_WITH, "fano", 0.4,
     ev("Eskinder Nega is associated with the Fano movement", "Wikipedia", WIKI + "Eskinder_Nega", False)),
    ("fano", RT.LOCATED_IN, "amhara", 0.85, None),
    ("amhara_sf", RT.ASSOCIATED_WITH, "amhara", 0.7, None),
    # Tigray War
    ("ev_tigray_war", RT.LOCATED_IN, "tigray", 0.95, None),
    ("endf", RT.PARTICIPATED_IN, "ev_tigray_war", 0.9,
     ev("ENDF was a principal combatant in the Tigray war", "Wikipedia", WIKI + "Tigray_war")),
    ("tdf", RT.PARTICIPATED_IN, "ev_tigray_war", 0.9, None),
    ("tplf", RT.PARTICIPATED_IN, "ev_tigray_war", 0.9, None),
    ("edf", RT.PARTICIPATED_IN, "ev_tigray_war", 0.85,
     ev("Eritrean forces fought alongside the ENDF in Tigray", "Wikipedia", WIKI + "Tigray_war")),
    ("amhara_sf", RT.PARTICIPATED_IN, "ev_tigray_war", 0.7, None),
    ("fano", RT.PARTICIPATED_IN, "ev_tigray_war", 0.6, None),
    ("ev_mai_kadra", RT.CONNECTED_TO, "ev_tigray_war", 0.7,
     ev("The Mai Kadra massacre occurred early in the Tigray war", "Wikipedia", WIKI + "Mai_Kadra_massacre", False)),
    ("ev_mai_kadra", RT.LOCATED_IN, "tigray", 0.7, None),
    ("ev_pretoria", RT.CONNECTED_TO, "ev_tigray_war", 0.9,
     ev("The Pretoria Agreement ended the Tigray war on 2 November 2022", "Wikipedia", WIKI + "Pretoria_Agreement")),
    ("au", RT.SUPERVISES, "ev_pretoria", 0.85, None),
    ("obasanjo", RT.PARTICIPATED_IN, "ev_pretoria", 0.8,
     ev("Olusegun Obasanjo mediated the AU-brokered Pretoria talks", "Wikipedia", WIKI + "Pretoria_Agreement")),
    ("endf", RT.PARTICIPATED_IN, "ev_pretoria", 0.8, None),
    ("tplf", RT.PARTICIPATED_IN, "ev_pretoria", 0.8, None),
    ("doc_pretoria", RT.REPORTED_BY, "ev_pretoria", 0.7, None),
    ("mike_hammer", RT.PARTICIPATED_IN, "ev_pretoria", 0.5,
     ev("US and EU envoys pressed for AU-led talks before Pretoria", "U.S. State Department",
        "https://2021-2025.state.gov/special-envoy-for-the-horn-of-africa-hammer-travels-to-belgium-kenya-and-ethiopia/")),
    ("annette_weber", RT.PARTICIPATED_IN, "ev_pretoria", 0.5, None),
    # Amhara / Fano war
    ("ev_amhara_war", RT.LOCATED_IN, "amhara", 0.9, None),
    ("fano", RT.PARTICIPATED_IN, "ev_amhara_war", 0.85,
     ev("Fano militias have fought the ENDF in Amhara since 2023", "Wikipedia", WIKI + "Amhara_offensive")),
    ("endf", RT.PARTICIPATED_IN, "ev_amhara_war", 0.85, None),
    ("fano", RT.CONNECTED_TO, "debark", 0.5,
     ev("Fano captured Debark and Metemma in a July 2024 offensive", "Wikipedia", WIKI + "Amhara_offensive", False)),
    ("fano", RT.CONNECTED_TO, "metemma", 0.5, None),
    ("ev_orthodox", RT.CONNECTED_TO, "eotc", 0.8, None),

    # ===================== Foreign military support (drones) =====================
    ("turkey", RT.CONNECTED_TO, "endf", 0.75,
     ev("Ethiopia signed a defence deal with Turkey for Bayraktar TB2 drones (Aug 2021)", "ECFR",
        "https://ecfr.eu/publication/deadly-skies-drone-warfare-in-ethiopia-and-the-future-of-conflict-in-africa/")),
    ("endf", RT.OWNS, "bayraktar", 0.7, None),
    ("turkey", RT.FOUNDED, "bayraktar", 0.6, None),
    ("erdogan", RT.MANAGES, "turkey", 0.85, None),
    ("uae", RT.CONNECTED_TO, "endf", 0.7,
     ev("UAE ran an air bridge of military support to Ethiopia's government", "Al Jazeera",
        "https://www.aljazeera.com/news/2021/11/25/uae-air-bridge-provides-military-support-to-ethiopia-govt")),
    ("mbz", RT.MANAGES, "uae", 0.85, None),
    ("iran", RT.CONNECTED_TO, "endf", 0.55,
     ev("Ethiopia acquired Iranian Mohajer-6 drones", "ECFR",
        "https://ecfr.eu/publication/deadly-skies-drone-warfare-in-ethiopia-and-the-future-of-conflict-in-africa/", False)),
    ("endf", RT.OWNS, "mohajer6", 0.5, None),
    ("china", RT.CONNECTED_TO, "endf", 0.55,
     ev("Ethiopia acquired Chinese Wing Loong drones", "ECFR",
        "https://ecfr.eu/publication/deadly-skies-drone-warfare-in-ethiopia-and-the-future-of-conflict-in-africa/", False)),
    ("endf", RT.OWNS, "wing_loong", 0.5, None),
    ("doc_ecfr_drones", RT.REPORTED_BY, "ev_tigray_war", 0.6, None),

    # ===================== Eritrea relations =====================
    ("isaias", RT.MANAGES, "eritrea", 0.9, None),
    ("isaias", RT.MANAGES, "edf", 0.8, None),
    ("isaias", RT.MANAGES, "pfdj", 0.8, None),
    ("abiy", RT.PARTICIPATED_IN, "ev_eth_eri_peace", 0.85,
     ev("Abiy and Isaias signed the 2018 peace agreement", "Wikipedia", WIKI + "Eritrea%E2%80%93Ethiopia_summit")),
    ("isaias", RT.PARTICIPATED_IN, "ev_eth_eri_peace", 0.85, None),
    ("ev_eth_eri_peace", RT.CONNECTED_TO, "ev_nobel", 0.7, None),
    ("abiy", RT.ATTENDED, "ev_nobel", 0.9,
     ev("Abiy Ahmed received the 2019 Nobel Peace Prize", "Wikipedia", WIKI + "Abiy_Ahmed")),
    ("eritrea", RT.CONNECTED_TO, "ev_eritrea_crisis", 0.7,
     ev("Ethiopia–Eritrea tensions are rising again over Red Sea access (2025–26)", "International Crisis Group",
        "https://www.crisisgroup.org/brf/africa/ethiopia-eritrea/b210-ethiopia-eritrea-and-tigray-powder-keg-horn-africa", False)),
    ("ethiopia", RT.CONNECTED_TO, "ev_eritrea_crisis", 0.7, None),
    ("ev_eritrea_crisis", RT.LOCATED_IN, "tigray", 0.6, None),
    ("eritrea", RT.ASSOCIATED_WITH, "tplf", 0.4,
     ev("Isaias reportedly pledged to protect the TPLF in a conflict with Ethiopia (2025)", "Foreign Policy",
        "https://foreignpolicy.com/2025/11/26/ethiopia-eritrea-tensions-red-sea-access-conflict/", False)),
    ("abiy", RT.CONNECTED_TO, "assab", 0.4,
     ev("Abiy called the loss of Red Sea access (Assab) a 'mistake' to be corrected", "Crisis Group",
        "https://www.crisisgroup.org/brf/africa/ethiopia-eritrea/b210-ethiopia-eritrea-and-tigray-powder-keg-horn-africa", False)),
    ("ethiopia", RT.CONNECTED_TO, "red_sea", 0.5, None),
    ("doc_icg_powderkeg", RT.REPORTED_BY, "ev_eritrea_crisis", 0.6, None),

    # ===================== Sea access: Somaliland / Somalia / Djibouti =====================
    ("ethiopia", RT.PARTICIPATED_IN, "ev_somaliland_mou", 0.85,
     ev("Ethiopia signed an MoU with Somaliland for Red Sea/Berbera access on 1 Jan 2024", "Wikipedia",
        WIKI + "2024_Ethiopia%E2%80%93Somaliland_memorandum_of_understanding")),
    ("somaliland", RT.PARTICIPATED_IN, "ev_somaliland_mou", 0.85, None),
    ("muse_bihi", RT.PARTICIPATED_IN, "ev_somaliland_mou", 0.7, None),
    ("ev_somaliland_mou", RT.CONNECTED_TO, "berbera", 0.8, None),
    ("ev_somaliland_mou", RT.CONNECTED_TO, "ethio_air", 0.6,
     ev("Somaliland was to receive a stake in Ethiopian Airlines under the MoU", "Al Jazeera",
        "https://www.aljazeera.com/news/2024/1/1/ethiopia-signs-agreement-to-use-somalilands-red-sea-port", False)),
    ("somalia", RT.CONNECTED_TO, "ev_somaliland_mou", 0.7,
     ev("Somalia condemned the MoU as a violation of its sovereignty", "Al Jazeera",
        "https://www.aljazeera.com/news/2024/1/1/ethiopia-signs-agreement-to-use-somalilands-red-sea-port")),
    ("hassan_smm", RT.MANAGES, "somalia", 0.8, None),
    ("irro", RT.MANAGES, "somaliland", 0.7, None),
    ("turkey", RT.SUPERVISES, "ev_ankara", 0.7,
     ev("Turkey brokered the Ankara Declaration between Ethiopia and Somalia (Dec 2024)", "Wikipedia",
        WIKI + "2024_Ethiopia%E2%80%93Somaliland_memorandum_of_understanding")),
    ("ethiopia", RT.PARTICIPATED_IN, "ev_ankara", 0.7, None),
    ("somalia", RT.PARTICIPATED_IN, "ev_ankara", 0.7, None),
    ("egypt", RT.ASSOCIATED_WITH, "somalia", 0.5,
     ev("Egypt and Somalia drew closer amid the Ethiopia–Somaliland dispute", "Atlantic Council",
        "https://www.atlanticcouncil.org/blogs/africasource/what-the-ethiopia-somaliland-deal-means-for-washingtons-strategy-in-the-red-sea/", False)),
    ("ethiopia", RT.CONNECTED_TO, "djibouti", 0.8,
     ev("Ethiopia routes the large majority of its trade through the Port of Djibouti", "Wikipedia",
        WIKI + "Ethio-Djibouti_Railways")),
    ("guelleh", RT.MANAGES, "djibouti", 0.8, None),
    ("addis_djibouti_rail", RT.CONNECTED_TO, "djibouti", 0.8, None),
    ("addis_djibouti_rail", RT.CONNECTED_TO, "addis", 0.8, None),
    ("erc", RT.MANAGES, "addis_djibouti_rail", 0.7, None),
    ("china", RT.FUNDED_BY, "addis_djibouti_rail", 0.5,
     ev("The Addis Ababa–Djibouti railway was built and financed by China", "Wikipedia",
        WIKI + "Ethio-Djibouti_Railways")),

    # ===================== GERD / Nile =====================
    ("ethiopia", RT.OWNS, "gerd", 0.9, None),
    ("gerd", RT.LOCATED_IN, "guba", 0.9, None),
    ("eep", RT.MANAGES, "gerd", 0.7, None),
    ("ev_gerd_inaug", RT.CONNECTED_TO, "gerd", 0.9,
     ev("Ethiopia inaugurated the GERD on 9 September 2025", "Al Jazeera",
        "https://www.aljazeera.com/news/2025/9/9/ethiopia-inaugurates-gerd-dam-amid-downstream-tensions-with-egypt-sudan")),
    ("egypt", RT.CONNECTED_TO, "gerd", 0.7,
     ev("Egypt views the GERD as an existential threat to its Nile water share", "Brookings",
        "https://www.brookings.edu/articles/the-controversy-over-the-grand-ethiopian-renaissance-dam/")),
    ("sudan", RT.CONNECTED_TO, "gerd", 0.6, None),
    ("sisi", RT.MANAGES, "egypt", 0.85, None),
    ("burhan", RT.MANAGES, "sudan", 0.7, None),
    ("cbe", RT.FUNDED_BY, "gerd", 0.4,
     ev("The GERD was financed largely through domestic bonds and contributions", "Wikipedia",
        WIKI + "Grand_Ethiopian_Renaissance_Dam", False)),

    # ===================== State enterprises (EIH portfolio) =====================
    ("eih", RT.OWNS, "ethio_air", 0.85,
     ev("EIH holds Ethiopia's major state-owned enterprises", "Addis Insight",
        "https://www.addisinsight.net/2024/12/04/ethiopian-investment-holdings-expands-its-portfolio-with-eight-key-additions/")),
    *[("eih", RT.OWNS, c, 0.85, None) for c in
      ["cbe", "ethio_tel", "eep", "erc", "dbe", "ipdc", "esl"]],
    ("ethio_air", RT.LOCATED_IN, "addis", 0.8, None),
    ("cbe", RT.LOCATED_IN, "addis", 0.7, None),
    ("metec", RT.ASSOCIATED_WITH, "endf", 0.7, None),

    # ===================== Economy & reforms =====================
    ("ethiopia", RT.PARTICIPATED_IN, "ev_birr_float", 0.85,
     ev("Ethiopia floated the birr in July 2024 to unlock a $3.4bn IMF programme", "Reuters/US News",
        "https://www.usnews.com/news/world/articles/2024-07-30/ethiopias-currency-dives-by-30-as-imf-backed-reforms-to-stabilize-the-economy-take-effect")),
    ("imf", RT.PARTICIPATED_IN, "ev_birr_float", 0.8, None),
    ("nbe", RT.PARTICIPATED_IN, "ev_birr_float", 0.7, None),
    ("ev_birr_float", RT.CONNECTED_TO, "ev_debt_deal", 0.7, None),
    ("imf", RT.PARTICIPATED_IN, "ev_debt_deal", 0.7, None),
    ("worldbank", RT.PARTICIPATED_IN, "ev_debt_deal", 0.7, None),
    ("ethiopia", RT.FUNDED_BY, "imf", 0.7,
     ev("IMF/World Bank deals (2024) underpin Ethiopia's ~$29B debt restructuring", "China-Global South Project",
        "https://chinaglobalsouth.com/analysis/attention-shifts-to-chinese-debt-following-ethiopias-imf-world-bank-deals/")),
    ("ethiopia", RT.FUNDED_BY, "worldbank", 0.7, None),
    ("doc_imf_report", RT.REPORTED_BY, "ev_birr_float", 0.6, None),
    ("ethiopia", RT.PARTICIPATED_IN, "ev_banking_lib", 0.8,
     ev("Ethiopia opened its banking sector to foreign banks in December 2024", "National Law Review",
        "https://natlawreview.com/article/ethiopia-opens-its-banking-sector-foreign-banks-and-investors-after-half-century")),
    ("nbe", RT.SUPERVISES, "ev_banking_lib", 0.7, None),
    # ESX & listings
    ("ecma", RT.SUPERVISES, "esx", 0.75, None),
    ("ev_esx_launch", RT.CONNECTED_TO, "esx", 0.85,
     ev("The Ethiopian Securities Exchange launched in January 2025", "ESX",
        "https://esx.et/ethiopian-securities-exchange-announces-the-official-listing-of-ethio-telecom-on-the-esx-main-market/")),
    ("ethio_tel", RT.PARTICIPATED_IN, "ev_ethiotel_ipo", 0.8,
     ev("Ethio Telecom ran a 10% IPO and listed on the ESX (first non-financial listing)", "Capital Ethiopia",
        "https://capitalethiopia.com/2026/05/25/ethio-telecom-debuts-on-ethiopian-securities-exchange-after-verifying-45000-shareholders/")),
    ("ethio_tel", RT.CONNECTED_TO, "esx", 0.7, None),
    ("awash_bank", RT.CONNECTED_TO, "esx", 0.6,
     ev("Awash Bank listed shares on the ESX main market", "Addis Insight",
        "https://www.addisinsight.net/2025/08/07/cbe-dashen-and-awash-intensify-competition-to-win-forex-hungry-clients/", False)),
    ("dashen_bank", RT.CONNECTED_TO, "esx", 0.6, None),
    # BRICS
    ("ethiopia", RT.PARTICIPATED_IN, "ev_brics", 0.8,
     ev("Ethiopia joined BRICS on 1 January 2024", "Wikipedia", WIKI + "BRICS")),
    ("ethiopia", RT.MEMBER_OF, "brics", 0.8, None),
    ("china", RT.MEMBER_OF, "brics", 0.8, None),

    # ===================== Private banks & business =====================
    ("al_amoudi", RT.FOUNDED, "midroc", 0.85,
     ev("Mohammed Al Amoudi founded MIDROC", "Wikipedia", WIKI + "Mohammed_Hussein_Al_Amoudi")),
    ("al_amoudi", RT.OWNS, "midroc_gold", 0.8,
     ev("Al Amoudi's MIDROC Gold is Ethiopia's largest mining company", "Billionaires.Africa",
        "https://www.billionaires.africa/2025/02/24/ethiopias-10-richest-businessmen/")),
    ("al_amoudi", RT.OWNS, "preem", 0.7, None),
    ("al_amoudi", RT.OWNS, "noc", 0.5, None),
    ("midroc", RT.OWNS, "derba", 0.7, None),
    ("midroc", RT.OWNS, "midroc_gold", 0.7, None),
    ("midroc_gold", RT.LOCATED_IN, "oromia", 0.5, None),
    ("preem", RT.LOCATED_IN, "sweden", 0.7, None),
    ("belayneh_k", RT.FOUNDED, "bkg", 0.85,
     ev("Belayneh Kindie founded the Belayneh Kindie Group", "Shore Africa",
        "https://shore.africa/2025/06/18/top-7-companies-owned-by-ethiopian-businessman-belayneh-kindie/")),
    ("belayneh_k", RT.OWNS, "bkg", 0.8, None),
    ("buzuayehu", RT.FOUNDED, "eahsc", 0.8,
     ev("Buzuayehu Tadele founded East African Holding", "Billionaires.Africa",
        "https://www.billionaires.africa/2025/02/24/ethiopias-10-richest-businessmen/")),
    ("samuel_tafesse", RT.FOUNDED, "sunshine", 0.8, None),
    ("bkg", RT.LOCATED_IN, "addis", 0.5, None),
    ("eahsc", RT.LOCATED_IN, "addis", 0.5, None),
    *[(b, RT.INVESTED_IN, "ethiopia", 0.5, None) for b in
      ["awash_bank", "dashen_bank", "abyssinia_bank", "coop_oromia", "zemen_bank", "wegagen_bank"]],
    ("wegagen_bank", RT.ASSOCIATED_WITH, "effort", 0.4, None),

    # ===================== Foreign economic actors =====================
    ("safaricom", RT.OWNS, "safaricom_et", 0.85,
     ev("Safaricom Ethiopia is the Kenyan-led consortium's subsidiary", "Wikipedia",
        WIKI + "Safaricom_Telecommunications_Ethiopia")),
    ("vodacom", RT.OWNS, "safaricom", 0.5, None),
    ("safaricom_et", RT.INVESTED_IN, "ethiopia", 0.8,
     ev("Safaricom's licence was the single largest FDI into Ethiopia", "Wikipedia",
        WIKI + "Safaricom_Telecommunications_Ethiopia")),
    ("safaricom_et", RT.CONNECTED_TO, "ethio_tel", 0.6, None),
    ("ruto", RT.MANAGES, "kenya", 0.8, None),
    ("safaricom", RT.LOCATED_IN, "kenya", 0.7, None),
    ("china", RT.INVESTED_IN, "ethiopia", 0.7,
     ev("China is Ethiopia's largest bilateral creditor (~25% of external debt)", "China-Global South Project",
        "https://chinaglobalsouth.com/analysis/attention-shifts-to-chinese-debt-following-ethiopias-imf-world-bank-deals/")),
    ("xi", RT.MANAGES, "china", 0.85, None),
    ("uae", RT.INVESTED_IN, "ethiopia", 0.6,
     ev("The UAE is a major investor in and ally of Abiy's government", "Al Jazeera",
        "https://www.aljazeera.com/news/2021/11/25/uae-air-bridge-provides-military-support-to-ethiopia-govt", False)),
    ("abiy", RT.ASSOCIATED_WITH, "mbz", 0.5, None),
    ("saudi", RT.INVESTED_IN, "ethiopia", 0.4, None),

    # ===================== USA / EU diplomacy & sanctions =====================
    ("usa", RT.CONNECTED_TO, "ev_agoa_susp", 0.8,
     ev("The US suspended Ethiopia from AGOA over the Tigray conflict (effective Jan 2022)", "Brookings",
        "https://www.brookings.edu/articles/the-exemplary-u-s-sanctions-regime-for-ethiopias-tigray-conflict-and-its-limitations/")),
    ("ev_agoa_susp", RT.CONNECTED_TO, "ev_tigray_war", 0.7, None),
    ("trump", RT.CONNECTED_TO, "ev_agoa_susp", 0.6,
     ev("President Trump extended Ethiopia's AGOA suspension to September 2026", "Ethiopian Policy",
        "https://ethiopianpolicy.com/2025/09/12/president-trump-extends-agoa-sanctions-on-ethiopia/", False)),
    ("trump", RT.MANAGES, "usa", 0.8, None),
    ("doc_eo14046", RT.REPORTED_BY, "ev_agoa_susp", 0.7, None),
    ("mike_hammer", RT.WORKS_FOR, "usa", 0.7, None),
    ("annette_weber", RT.WORKS_FOR, "eu", 0.7, None),
    ("eu", RT.CONNECTED_TO, "ev_tigray_war", 0.5, None),

    # ===================== Religion =====================
    ("abune_mathias", RT.MANAGES, "eotc", 0.8,
     ev("Abune Mathias is Patriarch of the Ethiopian Orthodox Tewahedo Church", "Wikipedia", WIKI + "Abune_Mathias")),
    ("abune_sawiros", RT.MANAGES, "oromia_synod", 0.7,
     ev("Abune Sawiros led the January 2023 breakaway synod", "Wikipedia",
        WIKI + "Abune_Mathias%E2%80%93Abune_Sawiros_schism")),
    ("oromia_synod", RT.CONNECTED_TO, "eotc", 0.6, None),
    ("ev_orthodox", RT.LOCATED_IN, "oromia", 0.6, None),
    ("abiy", RT.PARTICIPATED_IN, "ev_orthodox", 0.5,
     ev("Abiy mediated to resolve the Orthodox schism in February 2023", "Peninsula Qatar",
        "https://thepeninsulaqatar.com/article/16/02/2023/ethiopia-church-split-resolved-amid-social-media-suspension", False)),
    ("abune_mathias", RT.PARTICIPATED_IN, "ev_orthodox", 0.6, None),

    # ===================== Media =====================
    ("ebc", RT.ASSOCIATED_WITH, "ethiopia", 0.6, None),
    ("fana_bc", RT.ASSOCIATED_WITH, "pp", 0.4, None),
    ("walta", RT.ASSOCIATED_WITH, "pp", 0.4, None),
    ("omn", RT.REPORTED_BY, "ev_amhara_war", 0.3, None),
    ("addis_standard", RT.REPORTED_BY, "ev_tplf_split", 0.5, None),
    ("ethiopia_insight", RT.REPORTED_BY, "ev_eritrea_crisis", 0.5, None),
    ("tigrai_tv", RT.ASSOCIATED_WITH, "tplf", 0.4, None),
    ("esat", RT.ASSOCIATED_WITH, "ethiopia", 0.3, None),

    # ===================== International memberships =====================
    ("ethiopia", RT.MEMBER_OF, "au", 0.9, None),
    ("ethiopia", RT.MEMBER_OF, "igad", 0.9, None),
    ("ethiopia", RT.MEMBER_OF, "un", 0.9, None),
    ("moussa_faki", RT.WORKS_FOR, "au", 0.6, None),
    ("eritrea", RT.MEMBER_OF, "au", 0.7, None),
    ("somalia", RT.MEMBER_OF, "igad", 0.7, None),
    ("djibouti", RT.MEMBER_OF, "igad", 0.7, None),
]


async def _get_or_create(db, registry, created: set, slug):
    if slug in registry:
        return registry[slug]
    name, etype, props = ENTITIES[slug]
    existing = (await db.execute(
        select(Entity).where(Entity.name == name, Entity.type == etype)
    )).scalar_one_or_none()
    if existing is not None:
        registry[slug] = existing
        return existing
    entity = Entity(type=etype, name=name, aliases=[], description=None,
                    properties=props, confidence_score=0.5, is_ai_generated=False)
    db.add(entity)
    await db.flush()
    registry[slug] = entity
    created.add(slug)
    return entity


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    created_r = created_ev = 0
    created_slugs: set[str] = set()
    async with AsyncSessionLocal() as db:
        registry: dict[str, Entity] = {}
        for slug in ENTITIES:
            await _get_or_create(db, registry, created_slugs, slug)

        rels_with_evidence: list[uuid.UUID] = []
        for src, rtype, tgt, conf, evidence in RELS:
            s = await _get_or_create(db, registry, created_slugs, src)
            t = await _get_or_create(db, registry, created_slugs, tgt)
            exists = (await db.execute(
                select(Relationship).where(
                    Relationship.source_id == s.id,
                    Relationship.target_id == t.id,
                    Relationship.type == rtype,
                )
            )).scalar_one_or_none()
            if exists is not None:
                continue
            rel = Relationship(type=rtype, source_id=s.id, target_id=t.id,
                               confidence_score=conf, properties={}, is_ai_generated=False)
            db.add(rel)
            await db.flush()
            created_r += 1
            if evidence is not None:
                title, source, url, verified, stance = evidence
                db.add(Evidence(
                    title=title, source=source, url=url,
                    reliability_score=0.8, stance=stance,
                    verification_status=(VerificationStatus.VERIFIED if verified
                                         else VerificationStatus.UNVERIFIED),
                    is_ai_generated=False, relationship_id=rel.id,
                ))
                created_ev += 1
                if verified:
                    rels_with_evidence.append(rel.id)

        await db.commit()

        from app.services import confidence
        for rid in rels_with_evidence:
            await confidence.recompute_relationship_confidence(db, rid)
        await db.commit()

    print(f"Ethiopia dataset seeded: +{len(created_slugs)} entities, +{created_r} relationships, "
          f"+{created_ev} evidence items.")
    print("Next: restart the API and POST /api/v1/search/reindex to index the new entities.")


if __name__ == "__main__":
    asyncio.run(main())
