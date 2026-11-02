"""Generate the fictional due diligence data rooms as PDF files.

Run:  python data/demo/build_data_rooms.py

Every company, person, figure and document here is FICTIONAL and exists only
to demonstrate TaxPulse. Facts are deliberately spread across documents and
pages so the Profiler agent has to cite where each fact comes from.
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (ListFlowable, ListItem, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

OUT = Path(__file__).parent / "data_rooms"
FIRM = "Weber & Partner Steuerberatung (fictional firm)"

# ---------------------------------------------------------------------------
# Content. Each document = list of pages; each page = list of blocks:
#   ("h", text) heading · ("p", text) paragraph · ("ul", [items]) bullets
#   ("t", [[row], ...]) table, first row is the header
# ---------------------------------------------------------------------------

DATA_ROOMS = {
    "mueller_praezisionstechnik": {
        "company": "Müller Präzisionstechnik GmbH",
        "docs": {
            "01_Tax_Due_Diligence_Report.pdf": [
                [("h", "Tax Due Diligence Report – Project Alpine"),
                 ("p", "Target: Müller Präzisionstechnik GmbH, Reutlingen (Baden-Württemberg). "
                       "Buyer: Alpine Industrial Partners SCSp. Report date: 14 February 2024. "
                       "Closing: 28 March 2024."),
                 ("h", "Executive summary"),
                 ("p", "We identified no deal-breaking tax risks. Three areas require post-closing "
                       "attention: transfer pricing documentation for the Polish contract manufacturer, "
                       "readiness of the invoicing system for mandatory e-invoicing, and an unused "
                       "research allowance (Forschungszulage) potential."),
                 ("t", [["Area", "Risk", "Indicative exposure"],
                        ["Transfer pricing", "Medium", "EUR 0.4m – 0.9m"],
                        ["VAT / invoicing", "Medium", "Process risk"],
                        ["Research allowance", "Opportunity", "EUR 1.1m – 1.6m"],
                        ["Wage tax", "Low", "< EUR 50k"]])],
                [("h", "1. Corporate structure and tax group"),
                 ("p", "Müller Präzisionstechnik GmbH (the Company) is wholly owned by Müller Holding GmbH. "
                       "A fiscal unity (Organschaft) for corporate income tax and trade tax exists since 2016, "
                       "based on a profit and loss transfer agreement."),
                 ("p", "The Company holds 100% of Müller Precyzja Sp. z o.o., Wrocław (Poland), which "
                       "manufactures sub-assemblies exclusively for the Company with approx. 90 employees."),
                 ("p", "Business: CNC precision components for automotive suppliers (approx. 60% of sales) "
                       "and medical device manufacturers (approx. 40%). Export share approx. 55%, mainly EU, "
                       "Switzerland and the USA. Domestic B2B sales approx. EUR 21.7m in FY2023.")],
                [("h", "2. VAT"),
                 ("p", "The Company makes a high volume of domestic B2B supplies and intra-community supplies, "
                       "including chain transactions via the Polish subsidiary. Reporting was found to be "
                       "materially correct."),
                 ("p", "Invoices are generated in Sage 100 (on-premise, version 2019). The system produces PDF "
                       "invoices only and supports neither XRechnung nor ZUGFeRD. Management plans an ERP "
                       "migration \"in 2026 or later\"; no budget has been approved."),
                 ("h", "3. Wage tax"),
                 ("p", "22 managers use company cars; the 1% rule is applied correctly. Two vehicles are "
                       "fully electric (0.25% rule applied).")],
                [("h", "4. Transfer pricing"),
                 ("p", "Müller Precyzja is remunerated on a cost-plus basis with a markup of 5% under the "
                       "contract manufacturing agreement of 1 July 2019 (see data room document 03). "
                       "A Local File exists for FY2019–FY2021 but has not been updated since. The underlying "
                       "benchmarking study dates from 2019. A tax audit for FY2021–FY2023 is expected in 2026."),
                 ("h", "5. Research and development"),
                 ("p", "An internal R&D team of 14 FTE develops new machining processes for medical-grade "
                       "titanium implants. These are process innovations with technical uncertainty. R&D "
                       "personnel costs were approx. EUR 1.3m per year in FY2020–FY2023. No claim for the "
                       "research allowance under the FZulG has ever been filed and no BSFZ certificate exists."),
                 ("h", "6. Open points after closing"),
                 ("ul", ["Update Local File and benchmarking study before the 2026 audit",
                         "Evaluate a Forschungszulage claim for FY2020–FY2023",
                         "Assess e-invoicing readiness of the invoicing system"])],
            ],
            "02_Financial_Statements_FY2023.pdf": [
                [("h", "Annual Financial Statements FY2023 (extract)"),
                 ("p", "Müller Präzisionstechnik GmbH, Reutlingen. Financial year 1 January – 31 December 2023."),
                 ("t", [["Income statement (EUR m)", "FY2023", "FY2022"],
                        ["Revenue", "48.2", "44.9"],
                        ["Cost of materials", "(19.8)", "(18.6)"],
                        ["Personnel expenses", "(17.1)", "(16.0)"],
                        ["EBIT", "5.1", "4.4"],
                        ["Net income before profit transfer", "3.6", "3.0"]])],
                [("h", "Notes (extract)"),
                 ("ul", ["Average number of employees: 310 (FY2022: 296)",
                         "Purchases from affiliated company Müller Precyzja Sp. z o.o.: EUR 7.4m",
                         "Research and development expenses recognised in profit or loss: EUR 1.6m, "
                         "of which personnel costs EUR 1.3m",
                         "Leased production halls in Reutlingen and Metzingen (annual rent EUR 0.9m)"])],
            ],
            "03_Contract_Manufacturing_Agreement.pdf": [
                [("h", "Contract Manufacturing Agreement"),
                 ("p", "between Müller Präzisionstechnik GmbH, Reutlingen (Principal) and Müller Precyzja "
                       "Sp. z o.o., Wrocław (Manufacturer). Dated 1 July 2019."),
                 ("p", "§ 1 The Manufacturer produces machined sub-assemblies exclusively on behalf of the "
                       "Principal, using drawings and specifications provided by the Principal."),
                 ("p", "§ 2 The Principal bears market risk and inventory risk for finished goods.")],
                [("p", "§ 3 Remuneration. The Manufacturer receives its total operating costs plus a markup "
                       "of 5% (cost plus 5%). The markup was derived from a benchmarking study prepared in "
                       "2019."),
                 ("p", "§ 4 Review. The parties shall review the markup every three years. No review has been "
                       "documented to date."),
                 ("p", "§ 5 Term. The agreement runs for an indefinite period with six months' notice.")],
            ],
        },
    },
    "nordlicht_immobilien": {
        "company": "Nordlicht Immobilien GmbH & Co. KG",
        "docs": {
            "01_Tax_Due_Diligence_Report.pdf": [
                [("h", "Tax Due Diligence Report – Project Polarstern"),
                 ("p", "Target: Nordlicht Immobilien GmbH & Co. KG, Berlin. Buyer: Aurora Residential Fund "
                       "SCSp, Luxembourg. Report date: 3 August 2023. Closing: 29 September 2023."),
                 ("h", "Executive summary"),
                 ("p", "The transaction is structured as a share deal: the fund acquires 89.9% of the "
                       "partnership interests, a German family office (Hanseatic Family Office GmbH) acquires "
                       "10.1%. Key tax sensitivities are real estate transfer tax (RETT), the extended trade "
                       "tax reduction and the interest barrier."),
                 ("t", [["Area", "Risk", "Comment"],
                        ["RETT (share deal)", "High sensitivity", "90% threshold, 10-year holding periods"],
                        ["Trade tax – extended reduction", "Medium", "PV systems and operating equipment"],
                        ["Interest barrier", "Medium", "EUR 60m shareholder loan"],
                        ["VAT", "Low", "Option for commercial lettings"]])],
                [("h", "1. Structure and real estate transfer tax"),
                 ("p", "The 89.9% / 10.1% split keeps the acquisition below the 90% threshold of § 1 (2a) and "
                       "(2b) GrEStG. Any future transfer of interests within ten years must be monitored, "
                       "including a sale by the 10.1% co-investor."),
                 ("p", "The partnership is commercially imprinted (gewerblich geprägt) through its general "
                       "partner Nordlicht Verwaltungs GmbH and is therefore subject to trade tax.")],
                [("h", "2. Trade tax – extended reduction"),
                 ("p", "The partnership claims the extended trade tax reduction under § 9 No. 1 sentence 2 "
                       "GewStG for its rental income. Rooftop photovoltaic systems are operated on two "
                       "buildings (see property schedule, document 02) and electricity is fed into the grid."),
                 ("p", "Current feed-in income is below the statutory de minimis threshold. However, management "
                       "plans to install PV systems on six further buildings from 2025, which would "
                       "significantly increase this income. Two commercial units contain operating equipment "
                       "(Betriebsvorrichtungen) that should be reviewed.")],
                [("h", "3. Interest barrier and financing"),
                 ("p", "The fund granted a shareholder loan of EUR 60m at 6.5% interest (document 03). Net "
                       "interest expense exceeds EUR 3m; the partnership relies on the escape clause. "
                       "The arm's length nature of the interest rate is supported by a 2023 bank offer."),
                 ("h", "4. VAT"),
                 ("p", "Residential lettings are VAT-exempt. Commercial lettings (approx. 18% of rental income) "
                       "are partly subject to VAT by option; input VAT correction periods are running."),
                 ("h", "5. Open points after closing"),
                 ("ul", ["Monitor shareholder changes for 10 years (RETT)",
                         "Review PV expansion plan against the extended trade tax reduction",
                         "Re-test interest barrier escape clause annually"])],
            ],
            "02_Property_Schedule.pdf": [
                [("h", "Property Schedule as at 30 June 2023"),
                 ("t", [["#", "Property", "Use", "Rental income 2022 (EUR k)", "PV system"],
                        ["1", "Berlin, Prenzlauer Allee 112", "Residential", "1,240", "Yes (98 kWp)"],
                        ["2", "Berlin, Sonnenallee 45", "Mixed use", "1,010", "Yes (74 kWp)"],
                        ["3", "Berlin, Kantstraße 8", "Residential", "880", "No"],
                        ["4", "Potsdam, Brandenburger Str. 20", "Commercial", "760", "No"],
                        ["5-14", "10 further residential buildings", "Residential", "7,510", "No"],
                        ["", "Total", "", "11,400", "2 systems"]])],
                [("h", "Photovoltaic systems"),
                 ("p", "Electricity from both systems is fed into the public grid under the EEG. Feed-in income "
                       "2022: EUR 41k. The planned expansion to six further buildings from 2025 is estimated by "
                       "management to generate feed-in and tenant electricity income of approx. EUR 1.3m per "
                       "year once complete.")],
            ],
            "03_Shareholder_Loan_Agreement.pdf": [
                [("h", "Shareholder Loan Agreement"),
                 ("p", "Lender: Aurora Residential Fund SCSp, Luxembourg. Borrower: Nordlicht Immobilien GmbH "
                       "& Co. KG, Berlin. Dated 29 September 2023."),
                 ("p", "Principal amount: EUR 60,000,000. Interest: 6.5% p.a., payable annually. Term: 7 years. "
                       "The loan is subordinated to the senior bank financing."),
                 ("p", "The lender is a related party holding 89.9% of the interests in the borrower.")],
            ],
        },
    },
    "brightloop_software": {
        "company": "Brightloop Software GmbH",
        "docs": {
            "01_Tax_Due_Diligence_Report.pdf": [
                [("h", "Tax Due Diligence Report – Series B Financing"),
                 ("p", "Target: Brightloop Software GmbH, Munich. Lead investor: Northwind Ventures Fund IV LP "
                       "(USA). Round size: EUR 35m. Report date: 2 October 2024. Closing: 12 November 2024."),
                 ("h", "Executive summary"),
                 ("p", "The most significant tax exposure is the potential forfeiture of corporate tax loss "
                       "carryforwards of approx. EUR 21m following repeated ownership changes. Further points "
                       "concern the research allowance, invoicing and permanent establishment risk."),
                 ("t", [["Area", "Risk", "Indicative exposure"],
                        ["Loss carryforwards (§ 8c / § 8d KStG)", "High", "approx. EUR 6.3m future tax"],
                        ["Research allowance", "Medium", "EUR 0.6m (2023 claim)"],
                        ["Permanent establishment", "Medium", "FR / NL"],
                        ["VAT / invoicing", "Low", "Process risk"]])],
                [("h", "1. Ownership history and tax losses"),
                 ("p", "Corporate tax loss carryforwards amount to approx. EUR 21m at 31 December 2023. Through "
                       "the Seed (2020), Series A (2022) and Series B (2024) rounds, more than 50% of the shares "
                       "changed hands within five years (see cap table, document 02)."),
                 ("p", "Management intends to rely on the continuation-loss rule (§ 8d KStG). Since the Series A, "
                       "the company has shifted its focus from small logistics firms to enterprise customers "
                       "and launched a new route-optimisation product line in 2023. Documentation of business "
                       "continuity is incomplete.")],
                [("h", "2. Research allowance"),
                 ("p", "Research allowance claims were filed for 2022 and 2023 (approx. EUR 0.6m each). A BSFZ "
                       "certificate was obtained for the 2022 project only; the application for the 2023 "
                       "project (AI-based scheduling engine) has not been submitted."),
                 ("h", "3. Employee participation"),
                 ("p", "A virtual stock option plan covers 45 employees. Three senior hires received real shares "
                       "with deferred taxation under § 19a EStG.")],
                [("h", "4. VAT and invoicing"),
                 ("p", "SaaS subscriptions are invoiced through Stripe Billing as PDF invoices. Approx. 45% of "
                       "revenue is with German business customers; the remainder is cross-border B2B under the "
                       "reverse-charge mechanism. No structured e-invoice output is set up."),
                 ("h", "5. Permanent establishment"),
                 ("p", "Six employees work permanently from France (4) and the Netherlands (2). Some of them "
                       "negotiate customer contracts, which creates a risk of permanent establishments."),
                 ("h", "6. Open points after closing"),
                 ("ul", ["Build a defence file for the loss carryforwards",
                         "Submit the BSFZ application for the 2023 project",
                         "Assess permanent establishment risk for remote employees"])],
            ],
            "02_Cap_Table_History.pdf": [
                [("h", "Cap Table History (fully diluted)"),
                 ("t", [["Shareholder", "2019 (founding)", "Seed 2020", "Series A 2022", "Series B 2024"],
                        ["Founders (3)", "100%", "78%", "58%", "41%"],
                        ["Business angels", "–", "22%", "14%", "10%"],
                        ["Bavaria Tech Ventures", "–", "–", "28%", "20%"],
                        ["Northwind Ventures Fund IV", "–", "–", "–", "29%"]]),
                 ("p", "Cumulative transfer of shares to new shareholders between Seed 2020 and Series B 2024 "
                       "exceeds 50%.")],
            ],
            "03_Annual_Accounts_2023.pdf": [
                [("h", "Annual Accounts 2023 (extract)"),
                 ("t", [["EUR m", "2023", "2022"],
                        ["Revenue", "9.8", "5.4"],
                        ["Personnel expenses", "(11.9)", "(8.1)"],
                        ["Net loss", "(6.2)", "(5.7)"],
                        ["Tax loss carryforward at year end", "21.0", "14.8"]])],
                [("h", "Notes (extract)"),
                 ("ul", ["Average number of employees: 120, of which 48 in engineering",
                         "Customers: 310, of which 42 enterprise customers (2022: 6)",
                         "Revenue by region: Germany 45%, rest of DACH 20%, Benelux 22%, France 13%"])],
            ],
        },
    },
    "kaiser_dental": {
        "company": "Kaiser Dental MVZ GmbH",
        "docs": {
            "01_Tax_Due_Diligence_Report.pdf": [
                [("h", "Tax Due Diligence Report – Project Smile"),
                 ("p", "Target: Kaiser Dental MVZ GmbH, Hamburg. Buyer: Elbe Health Holding GmbH. "
                       "Report date: 18 April 2024. Closing: 31 May 2024."),
                 ("h", "Executive summary"),
                 ("p", "The target operates four dental care centres (MVZ) in Hamburg with 64 employees and "
                       "revenue of EUR 11.2m (2023). We identified no material tax risks."),
                 ("t", [["Area", "Risk", "Comment"],
                        ["Corporate / trade tax", "Low", "Profitable, no loss carryforwards"],
                        ["VAT", "Low", "Dental treatments VAT-exempt (§ 4 No. 14 UStG)"],
                        ["Wage tax", "Low", "Correctly applied"]])],
                [("h", "1. Business and VAT"),
                 ("p", "Revenue consists almost entirely of VAT-exempt dental treatments billed to patients and "
                       "statutory health insurers. Taxable supplies (e.g. cosmetic whitening) are below 2% of "
                       "revenue. There are no business customers."),
                 ("h", "2. Structure"),
                 ("p", "Single German entity, no subsidiaries, no foreign related parties, no research "
                       "activities. All premises are leased."),
                 ("h", "3. Open points after closing"),
                 ("ul", ["None material"])],
            ],
        },
    },
}


def build():
    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Heading2"], textColor=colors.HexColor("#1e3a5f"), spaceAfter=6)
    p = ParagraphStyle("p", parent=styles["BodyText"], fontSize=10, leading=14, spaceAfter=6)

    for client_id, room in DATA_ROOMS.items():
        folder = OUT / client_id
        folder.mkdir(parents=True, exist_ok=True)
        for filename, pages in room["docs"].items():
            title = filename[3:-4].replace("_", " ")

            def decorate(canvas, doc, company=room["company"], title=title):
                canvas.saveState()
                canvas.setFont("Helvetica", 8)
                canvas.setFillColor(colors.grey)
                canvas.drawString(20 * mm, 287 * mm, f"{company} · {title}")
                canvas.drawRightString(190 * mm, 287 * mm, FIRM)
                canvas.drawString(20 * mm, 10 * mm, "FICTIONAL DEMO DOCUMENT – created for TaxPulse, not real data")
                canvas.drawRightString(190 * mm, 10 * mm, f"Page {doc.page}")
                canvas.restoreState()

            story = []
            for i, page in enumerate(pages):
                if i:
                    story.append(PageBreak())
                for kind, content in page:
                    if kind == "h":
                        story.append(Paragraph(content, h))
                    elif kind == "p":
                        story.append(Paragraph(content, p))
                    elif kind == "ul":
                        story.append(ListFlowable([ListItem(Paragraph(x, p)) for x in content],
                                                  bulletType="bullet", leftIndent=12))
                    elif kind == "t":
                        t = Table(content, hAlign="LEFT")
                        t.setStyle(TableStyle([
                            ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef5")),
                            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4d0")),
                            ("PADDING", (0, 0), (-1, -1), 4),
                        ]))
                        story += [Spacer(1, 4), t, Spacer(1, 8)]
            SimpleDocTemplate(str(folder / filename), pagesize=A4, topMargin=25 * mm,
                              bottomMargin=20 * mm, leftMargin=20 * mm, rightMargin=20 * mm,
                              title=f"{room['company']} – {title}").build(
                story, onFirstPage=decorate, onLaterPages=decorate)
            print("built", folder.name, filename, f"({len(pages)} pages)")


if __name__ == "__main__":
    build()
