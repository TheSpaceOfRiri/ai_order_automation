"""Parser check against the ACTUAL pdfplumber text layer of Order_confirmtion.pdf.

Note how the Bengali comes out garbled (broken font/ToUnicode CMap) while
English fields, digits, and the item blocks extract perfectly.
"""
from core.order_parser import OrderParser

# Verbatim text layer extracted from the real PDF (Bengali is mojibake).
REAL = """Order confirmed
Name, Phone Number, Address
Name : Sunny
Address : 250/2, Meherchori, Rajshahi
Mobile No : 01749462068
Bill: 820 taka cash on delivery
Note:
Items:
1. Product: Lost
Color: Black
Size: L
Quantity: 1
2. Product: Pokemon
Color: White
Size: L
Quantity: 1
Order confirmed
Name, Phone Number, Address
Ripon Ahmed
Zilla - Bogura
Thana - Adamdighi
Area - Santahar Pourosova
Adamdighi Santahar
01991181360
Bill: 1050 taka cash on delivery
Note:
Items:
1. Product: Pokemon
Color: Navy Blue
Size: M
Quantity: 1
2. Product: Paris Romantic City
Color: Patrol Blue
Size: M
Quantity: 1
3. Product: Lost
Color: Mint
Size: M
Quantity: 1
Order confirmed
Name, Phone Number, Address
নাম: জাবেদ
ঠিকানা: জজলা, ঢাকা উপবজলা/থানা, এরিযা. ওযািী
০১৬১৯৭৫৬৯৯৮
01619756998
Bill: 1050 taka cash on delivery
Note:
Items:
1. Product: Lost
Color: White
Size: XL
Quantity: 2
2. Product: Paris Romantic City
Color: Bottle Green
Size: XL
Quantity: 1
Order confirmed
Name, Phone Number, Address
জমাোঃ শারমম
ঠিকানা মুরি ভারিি জকানা জ ালুকপুি মাদিাস আরিি উরদদন িিাজী েড়ীি দিজা
জজলা জভালা উপবজলা তজমু রদদন থানাও তজমু রদদন এরিযা জ ালকপুি
জিান নাোঃ 01797084320
Bill: 1050 taka cash on delivery
Note:
Items:
1. Product: Pokemon
Color: Black
Size: M
Quantity: 1
2. Product: Lost
Color: Mint
Size: M
Quantity: 1
3. Product: Pokemon
Color: Patrol Blue
Size: M
Quantity: 1
Order confirmed
Name, Phone Number, Address
নাম: জেদাবযত উল্লাে
কলারতযা, জ ন্নাথপুি রতন িাস্তাি জমাড়
জদাকান: আল মরদনা জেরলকম
ঢাকা, জকিারন ঞ্জ
01328268868
Bill: 410 taka cash on delivery
Note:
Items:
1. Product: Paris Romantic City
Color: Bottle Green
Size: L
Quantity: 1
"""


def main() -> None:
    customers = OrderParser(price_per_piece=350).parse(REAL)
    print(f"Parsed {len(customers)} customer(s):\n")
    for i, c in enumerate(customers, 1):
        print(f"Customer {i}: {c.name}")
        print(f"  Last name field: {c.last_name_marker}")
        print(f"  Phone   : {c.phone}")
        print(f"  Address : {c.address}")
        print(f"  City    : {c.city}   Shipping: {c.shipping}")
        print(f"  Bill    : {c.bill_amount}  (standard total = {c.total_quantity} x 350 = {c.total_quantity*350})")
        for it in c.items:
            print(f"    - {it.product!r} | {it.color} / {it.size} x{it.quantity}")
        print()


if __name__ == "__main__":
    main()
