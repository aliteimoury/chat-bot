import cloudscraper
import json
import time
import re
import os

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)


def clean_product_name(title_fa, category_type):
    if category_type == "laptop":
        # پیدا کردن اولین جایی که پردازنده (i3, i5, Ryzen) یا رم و حافظه (GB, TB) شروع می‌شه
        pattern = r'(?i)\s*-\s*(i\d|Ryzen|Core|Pentium|Celeron|\d+\s*GB|\d+\s*TB|SSD|HDD)'
        clean_name = re.split(pattern, title_fa)[0].strip()
        # جایگزینی کلمات طولانی برای زیبایی بیشتر (اختیاری)
        clean_name = clean_name.replace("لپ تاپ", "لپ‌تاپ").replace(" اینچی", '"')
        return clean_name
    else:
        # همون منطق قبلی برای موبایل
        pattern = r'\s+(دو سیم|تک سیم|ظرفیت|حافظه|با رم|رم|نسخه|پک|نات اکتیو|-)'
        clean_name = re.split(pattern, title_fa)[0].strip()
        return clean_name.replace("گوشی موبایل", "گوشی")


def get_phone_details(product_id):
    url = f"https://api.digikala.com/v2/product/{product_id}/"
    try:
        response = scraper.get(url, timeout=15)
        if response.status_code == 200:
            return response.json().get("data", {}).get("product", {})
    except Exception as e:
        print(f"  [!] خطا در دریافت جزئیات محصول {product_id}: {e}")
    return None


def parse_specifications(product_detail, category_type):
    specifications = product_detail.get("specifications", [])
    desc_string = ""

    # گرفتن خلاصه توضیحات
    summary = product_detail.get("review", {}).get("summary", "")
    if summary:
        summary = summary.replace("<p>", "").replace("</p>", "").replace("<br>", " ")
        desc_string = f"{summary[:80]}..."

    # --- مشخصات لپ‌تاپ ---
    if category_type == "laptop":
        cpu_series, cpu_model = "", ""
        ram_cap, ram_upgrade = "", ""
        gpu_maker, gpu_model = "", ""
        storage_cap, display_size = "نامشخص", "نامشخص"

        for group in specifications:
            for attr in group.get("attributes", []):
                title = str(attr.get("title", "")).strip().replace('\u200c', ' ')
                vals = attr.get("values", [])
                if not vals: continue

                val = vals[0]
                if isinstance(val, dict): val = val.get("title", "نامشخص")
                val = str(val).strip()

                # استخراج دقیق و نقطه‌زن فیلدها
                if title == "سری پردازنده":
                    cpu_series = val
                elif title == "مدل پردازنده":
                    cpu_model = val
                elif title == "ظرفیت حافظه RAM":
                    ram_cap = val
                elif title == "قابلیت ارتقای حافظه" or "ارتقا RAM" in title:
                    ram_upgrade = val
                elif title == "سازنده پردازنده گرافیکی":
                    gpu_maker = val
                elif title == "مدل پردازنده گرافیکی":
                    gpu_model = val
                elif title == "ظرفیت حافظه داخلی":
                    storage_cap = val
                elif title == "اندازه صفحه نمایش":
                    display_size = val

        # ترکیب مقادیر خرد شده با هم
        cpu = f"{cpu_series} {cpu_model}".strip() if (cpu_series or cpu_model) else "نامشخص"
        gpu = f"{gpu_maker} {gpu_model}".strip() if (gpu_maker or gpu_model) else "نامشخص"

        # مدیریت نمایش رم و قابلیت ارتقا
        ram = ram_cap if ram_cap else "نامشخص"
        if ram_upgrade and ram_upgrade != "نامشخص":
            ram += f" (قابلیت ارتقا: {ram_upgrade})"

        specs_string = f"پردازنده {cpu} - رم {ram} - گرافیک {gpu} - حافظه {storage_cap} - نمایشگر {display_size}"
        return specs_string, desc_string

    # --- مشخصات موبایل ---
    else:
        ram, storage, camera, battery, display = "نامشخص", "نامشخص", "نامشخص", "نامشخص", "نامشخص"
        for group in specifications:
            for attr in group.get("attributes", []):
                title = str(attr.get("title", "")).replace('\u200c', ' ')
                vals = attr.get("values", [])
                if not vals: continue

                val = vals[0]
                if isinstance(val, dict): val = val.get("title", "نامشخص")
                val = str(val)

                if "حافظه داخلی" in title:
                    storage = val
                elif "مقدار RAM" in title or "حافظه رم" in title or title == "رم":
                    ram = val
                elif "رزولوشن عکس" in title or "دوربین اصلی" in title or "دوربین" in title:
                    if camera == "نامشخص": camera = val
                elif "ظرفیت باتری" in title or "مشخصات باتری" in title or "باتری" in title:
                    if battery == "نامشخص": battery = val
                elif "اندازه" in title or "صفحه نمایش" in title or "ابعاد" in title:
                    if "اینچ" in val or display == "نامشخص": display = val

        specs_string = f"رم {ram} - حافظه {storage} - دوربین {camera} - باتری {battery}"
        return specs_string, desc_string

def get_best_price(search_product, detail_product):
    selling_price = 0

    default_variant_search = search_product.get("default_variant", {})
    if default_variant_search:
        selling_price = default_variant_search.get("price", {}).get("selling_price", 0)

    if selling_price == 0 and detail_product:
        default_variant_detail = detail_product.get("default_variant", {})
        if default_variant_detail:
            selling_price = default_variant_detail.get("price", {}).get("selling_price", 0)

    if selling_price > 0:
        return f"{int(selling_price / 10):,} تومان"
    else:
        return "ناموجود"


def load_existing_data(filename):
    """خواندن اطلاعات قبلی از فایل JSON (در صورت وجود)"""
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"[{len(data)} محصول از قبل در فایل '{filename}' موجود است.]")
                return data
        except json.JSONDecodeError:
            print(f"[!] فایل '{filename}' خراب است یا ساختار درستی ندارد. از صفر شروع می‌کنیم.")
            return []
    return []


def scrape_digikala_phones(target_new_products=5, category_type="mobile"):
    """
    دریافت محصولات دیجی‌کالا.
    ...
    """
    if category_type == "laptop":
        search_url = "https://api.digikala.com/v1/categories/notebook-netbook-ultrabook/search/"
        cat_name = "لپ‌تاپ"
    else:
        search_url = "https://api.digikala.com/v1/categories/mobile-phone/search/"
        cat_name = "موبایل"

    output_filename = "products.json"

    # 1. خواندن داده‌های قبلی
    existing_products = load_existing_data(output_filename)

    # ایجاد یک لیست از اسامی (یا آیدی‌های) محصولاتی که از قبل داریم برای بررسی سریع‌تر تکراری‌ها
    existing_names = [p.get("name") for p in existing_products]

    # پیدا کردن آخرین ID استفاده شده برای اینکه آیدی محصولات جدید از ادامه آن شماره‌گذاری شود
    last_id = max([p.get("id", 0) for p in existing_products]) if existing_products else 0
    product_id_counter = last_id + 1

    new_products_found = 0
    page = 1

    print(f"\nشروع استخراج... هدف: پیدا کردن {target_new_products} محصول جدید و غیر تکراری.")

    while new_products_found < target_new_products:
        params = {"page": page}
        try:
            print(f"\n--- در حال بررسی صفحه {page} ---")
            res = scraper.get(search_url, params=params, timeout=15)

            if res.status_code != 200:
                print(f"خطا در دریافت صفحه {page}. کد وضعیت: {res.status_code}")
                page += 1
                time.sleep(2)
                continue

            products = res.json().get("data", {}).get("products", [])
            if not products:
                print("محصول دیگری در دیجی‌کالا یافت نشد. پایان جستجو.")
                break

            for p in products:
                # اگر به تعداد هدف رسیدیم، از حلقه خارج می‌شویم
                if new_products_found >= target_new_products:
                    break

                original_title = p.get("title_fa", "بدون نام")
                short_title = clean_product_name(original_title, category_type)

                # بررسی تکراری بودن بر اساس نام کوتاه شده
                if short_title in existing_names:
                    print(f"  [تکراری - رد شد] {short_title}")
                    continue

                print(f"  [محصول جدید یافت شد] در حال دریافت: {short_title}...")

                p_id = p.get("id")
                product_detail = get_phone_details(p_id)

                if product_detail:
                    specs, description = parse_specifications(product_detail, category_type)
                else:
                    specs, description = "نامشخص", "نامشخص"

                price_toman = get_best_price(p, product_detail)

                formatted_product = {
                    "id": product_id_counter,
                    "name": short_title,
                    "category": cat_name,
                    "price": price_toman,
                    "specs": specs,
                    "description": description
                }

                # اضافه کردن محصول جدید به لیست اصلی و لیست اسامی
                existing_products.append(formatted_product)
                existing_names.append(short_title)

                product_id_counter += 1
                new_products_found += 1
                time.sleep(2)

            # رفتن به صفحه بعد دیجی‌کالا
            page += 1

        except Exception as e:
            print(f"خطا در حین بررسی صفحه {page}: {e}")
            break

    # 3. ذخیره مجدد تمام محصولات (قبلی‌ها + جدیدها) در فایل
    if new_products_found > 0:
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(existing_products, f, ensure_ascii=False, indent=4)
        print(f"\nعملیات با موفقیت پایان یافت! {new_products_found} محصول جدید به فایل اضافه شد.")
        print(f"تعداد کل محصولات در فایل: {len(existing_products)}")
    else:
        print("\nهیچ محصول جدیدی یافت نشد. فایل تغییری نکرد.")


if __name__ == "__main__":
    # در اینجا مشخص می‌کنید که در هر بار اجرا، چند محصول *جدید* پیدا کند.
    # الان روی 5 تنظیم شده است. اگر می‌خواهید تعداد بیشتری پیدا کند، عدد را تغییر دهید.
    scrape_digikala_phones(target_new_products=25)