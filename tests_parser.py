"""Standalone parser check against the real PDF format.

Run:  python3 tests_parser.py
"""
from core.order_parser import OrderParser

SAMPLE = """
**Order confirmed ✅**
Name, Phone Number, Address ⬇️

Name : Sunny
Address : 250/2, Meherchori, Rajshahi
Mobile No : 01749462068

Bill: 820 taka cash on delivery ✅
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

---

**Order confirmed ✅**
Name, Phone Number, Address ⬇️

Ripon Ahmed
Zilla - Bogura
Thana - Adamdighi
Area - Santahar Pourosova
Adamdighi Santahar
01991181360

Bill: 1050 taka cash on delivery ✅
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

---

**Order confirmed ✅**
Name, Phone Number, Address ⬇️

নাম: জাবেদ
ঠিকানা: জেলা, ঢাকা উপজেলা/থানা, এরিয়া. ওয়ারী
০১৬১৯৭৫৬৯৯৮
01619756998

Bill: 1050 taka cash on delivery ✅
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

---

**Order confirmed ✅**
Name, Phone Number, Address ⬇️

মোঃ শামিম
ঠিকানা মুচি ভারির কোনা গোলুকপুর মাদরাস আফির উদিদন ফরাজী বড়ীর দরজা
জেলা ভোলা উপজেলা তজুমদিদন থানাও তজুমদিদন এরিয়া গোলকপুর
ফোন নাঃ 01797084320

Bill: 1050 taka cash on delivery ✅
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

---

**Order confirmed ✅**
Name, Phone Number, Address ⬇️

নাম: হেদায়েত উল্লাহ
কলাতিয়া, জগন্নাথপুর তিন রাস্তার মোড়
দোকান: আল মদিনা টেলিকম
ঢাকা, কেরানিগঞ্জ
01328268868

Bill: 410 taka cash on delivery ✅
Note:

Items:

1. Product: Paris Romantic City
   Color: Bottle Green
   Size: L
   Quantity: 1
"""


def main() -> None:
    customers = OrderParser(price_per_piece=350).parse(SAMPLE)
    print(f"Parsed {len(customers)} customer(s):\n")
    for i, c in enumerate(customers, 1):
        print(f"Customer {i}: {c.name}")
        print(f"  Phone   : {c.phone}")
        print(f"  Address : {c.address}")
        print(f"  City    : {c.city}   Shipping: {c.shipping}   Payment: {c.payment}")
        print(f"  Bill    : {c.bill_amount}   Notes: {c.notes!r}")
        print(f"  Items   ({len(c.items)}):")
        for it in c.items:
            print(f"    - {it.product!r} | color={it.color!r} size={it.size} qty={it.quantity}")
        print()


if __name__ == "__main__":
    main()
