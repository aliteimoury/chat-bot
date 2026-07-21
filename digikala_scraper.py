import cloudscraper
import json
import time
import re
import os

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)


STOP_PATTERN = re.compile(
    r'(ظرفیت|حافظه|دو سیم|تک سیم|نسخه\s|پک\s|نات اکتیو|\sبا\s|مقاوم\s|قابل\s|دارای\s|مناسب\s|\(|\s-\s|\s-$)'
)

def clean_phone_name(title_fa):
    clean_name = title_fa
    match = STOP_PATTERN.search(clean_name)
    if match:
        clean_name = clean_name[:match.start()]

    clean_name = clean_name.replace("گوشی موبایل", "گوشی")
    clean_name = clean_name.replace("هدفون", "")
    clean_name = clean_name.replace("هندزفری", "")
    clean_name = clean_name.replace("بلوتوثی", "")
    clean_name = clean_name.replace("بی سیم", "")
    clean_name = clean_name.replace("بیسیم", "")

    clean_name = re.sub(r'\s+', ' ', clean_name).strip()

    if not clean_name:
        clean_name = title_fa[:50]

    return clean_name


def get_phone_details(product_id):
    url = f"https://api.digikala.com/v2/product/{product_id}/"
    try:
        response = scraper.get(url, timeout=15)
        if response.status_code == 200:
            data = response.json().get("data", {}).get("product", {})
            # اطمینان از وجود categories
            if "categories" not in data:
                data["categories"] = []
            return data
    except Exception as e:
        print(f"  [!] خطا در دریافت جزئیات محصول {product_id}: {e}")
    return None


def parse_specifications(product_detail):
    # تشخیص دسته محصول از طریق categories
    category = ""
    category_list = product_detail.get("categories", [])

    # لیست کلمات کلیدی برای هر دسته
    headphone_keywords = ["هدفون", "هندزفری", "headphone", "headset", "earphone"]
    mobile_keywords = ["موبایل", "گوشی", "mobile", "phone"]
    tablet_keywords = ["تبلت", "tablet", "ipad"]

    for cat in category_list:
        cat_title = cat.get("title", "").lower()
        if any(keyword in cat_title for keyword in headphone_keywords):
            category = "هدفون"
            break
        elif any(keyword in cat_title for keyword in mobile_keywords):
            category = "موبایل"
            break
        elif any(keyword in cat_title for keyword in tablet_keywords):
            category = "تبلت"
            break

# اگر دسته‌بندی هدفون بود، از تابع مخصوص استفاده کن
    if category == "هدفون":
        return parse_headphone_specifications(product_detail)

    ram, storage, camera, battery, display = "نامشخص", "نامشخص", "نامشخص", "نامشخص", "نامشخص"
    specifications = product_detail.get("specifications", [])
    
    # متغیر برای ذخیره موقت دوربین اصلی و سلفی
    camera_main = "نامشخص"
    camera_selfie = "نامشخص"
    camera_raw_value = ""  # برای ذخیره مقدار خام دوربین
    
    for group in specifications:
        for attr in group.get("attributes", []):
            title = str(attr.get("title", "")).replace('\u200c', ' ').strip()
            values_list = attr.get("values", [])
            
            if not values_list: 
                continue
            
            value = values_list[0]
            if isinstance(value, dict):
                value = value.get("title", "نامشخص")
            value = str(value).strip()
            
            # ============ پردازش حافظه داخلی (Storage) ============
            storage_keywords = ["حافظه داخلی", "ظرفیت حافظه", "حافظه", "فضای ذخیره‌سازی"]
            if any(keyword in title for keyword in storage_keywords):
                if "گیگابایت" in value or "GB" in value or "ترابایت" in value:
                    storage = value
                    continue
            
            # ============ پردازش رم (RAM) ============
            ram_keywords = ["مقدار RAM", "حافظه رم", "رم", "RAM", "حافظه موقت"]
            if any(keyword in title for keyword in ram_keywords):
                if "گیگابایت" in value or "GB" in value:
                    ram = value
                    continue
            
            # ============ پردازش دوربین (Camera) - بهبود یافته با اولویت مگاپیکسل ============
            # بررسی دوربین اصلی (عقب)
            main_camera_keywords = ["دوربین اصلی", "دوربین عقب", "رزولوشن دوربین اصلی", "کیفیت دوربین اصلی"]
            is_main_camera = any(keyword in title for keyword in main_camera_keywords)
            
            # بررسی دوربین سلفی (جلو)
            selfie_keywords = ["دوربین سلفی", "دوربین جلو", "رزولوشن دوربین سلفی", "کیفیت دوربین سلفی"]
            is_selfie = any(keyword in title for keyword in selfie_keywords)
            
            # ===== استخراج مگاپیکسل از مقدار =====
            # الگوهای مختلف برای پیدا کردن مگاپیکسل
            mp_patterns = [
                r'(\d+\.?\d*)\s*(مگاپیکسل|مگاپیکسلی|MP|mp)',  # 48 مگاپیکسل یا 48MP
                r'(\d+\.?\d*)\s*(مگا پیکسل|مگا پیکسلی)',  # 48 مگا پیکسل
                r'(\d+)\s*[\u0660-\u0669]+'  # اعداد فارسی
            ]
            
            mp_value = None
            for pattern in mp_patterns:
                mp_match = re.search(pattern, value, re.IGNORECASE)
                if mp_match:
                    # استخراج عدد
                    num = re.search(r'(\d+\.?\d*)', mp_match.group(0))
                    if num:
                        mp_value = f"{num.group(1)} مگاپیکسل"
                        break
            
            # اگر مقدار مگاپیکسل پیدا شد
            if mp_value:
                # اگر دوربین اصلی بود یا کلید "دوربین" داشت
                if is_main_camera or "دوربین" in title:
                    if camera_main == "نامشخص" or is_main_camera:
                        camera_main = mp_value
                        continue
                elif is_selfie:
                    camera_selfie = mp_value
                    continue
                else:
                    # اگر کلید خاصی نداشت ولی مگاپیکسل داشت، به عنوان دوربین اصلی در نظر بگیر
                    if camera_main == "نامشخص" and "سلفی" not in title and "جلو" not in title:
                        camera_main = mp_value
                        continue
            
            # اگر مگاپیکسل پیدا نشد، ولی مقدار دوربین اصلی بود
            if is_main_camera and camera_main == "نامشخص":
                # بررسی اعداد در مقدار
                num_match = re.search(r'(\d+)\s*(مگاپیکسل|MP|mega)', value, re.IGNORECASE)
                if num_match:
                    camera_main = f"{num_match.group(1)} مگاپیکسل"
                elif "ماژول" not in value and len(value) > 5:
                    # اگر مقدار مفیدی بود ذخیره کن
                    camera_main = value
                continue
            
            # ============ پردازش باتری (Battery) ============
            battery_keywords = ["ظرفیت باتری", "باتری", "مشخصات باتری", "شارژ باتری"]
            for keyword in battery_keywords:
                if keyword in title:
                    if battery == "نامشخص":
                        # استخراج عدد از مقدار باتری
                        battery_match = re.search(r'(\d+)\s*(میلی‌آمپر|mAh|وات‌ساعت|Wh)', value, re.IGNORECASE)
                        if battery_match:
                            battery = battery_match.group(0)
                        else:
                            battery = value
                        break
            
            # ============ پردازش نمایشگر (Display) ============
            display_keywords = ["صفحه نمایش", "نمایشگر", "اندازه صفحه", "ابعاد صفحه"]
            for keyword in display_keywords:
                if keyword in title:
                    if "اینچ" in value or display == "نامشخص":
                        display = value
                        break

    # انتخاب دوربین اصلی (اگر پیدا شد)
    if camera_main != "نامشخص":
        camera = camera_main
    # اگر دوربین اصلی پیدا نشد، از دوربین سلفی استفاده کن
    elif camera_selfie != "نامشخص":
        camera = f"سلفی {camera_selfie}"
    else:
        camera = "نامشخص"

    specs_string = f"رم {ram} - حافظه {storage} - دوربین {camera} - باتری {battery}"
    desc_string = f"نمایشگر {display}"
    
    summary = product_detail.get("review", {}).get("summary", "")
    if summary:
        summary = summary.replace("<p>", "").replace("</p>", "").replace("<br>", " ")
        desc_string += f" - {summary[:100]}..."
    
    return specs_string, desc_string


def parse_headphone_specifications(product_detail):
    """پردازش مشخصات مخصوص هدفون"""
    headphone_type = "نامشخص"      # بی سیم / سیمی
    battery_life = "نامشخص"        # تعداد روز یا میلی آمپر
    noise_canceling = "نامشخص"     # دارد / ندارد
    bluetooth_version = "نامشخص"   # نسخه بلوتوث
    
    specifications = product_detail.get("specifications", [])
    
    for group in specifications:
        for attr in group.get("attributes", []):
            title = str(attr.get("title", "")).replace('\u200c', ' ').strip()
            values_list = attr.get("values", [])
            
            if not values_list:
                continue
            
            value = values_list[0]
            if isinstance(value, dict):
                value = value.get("title", "نامشخص")
            value = str(value).strip()
            
            # ============ تشخیص نوع هدفون (بی سیم / سیمی) ============
            if "نوع" in title or "اتصال" in title or "رابط" in title:
                if "بی سیم" in value or "بیسیم" in value or "وایرلس" in value or "wireless" in value.lower():
                    headphone_type = "بی سیم"
                elif "سیمی" in value or "با سیم" in value or "wired" in value.lower():
                    headphone_type = "سیمی"
                continue
            
            # ============ تشخیص باتری (ساعت یا روز) - بهبود یافته ============
            if "باتری" in title or "شارژ" in title or "عمر باتری" in title:
                # استخراج عدد و واحد از مقدار
                # الگوی: عدد + ساعت/روز
                match = re.search(r'(\d+\.?\d*)\s*(ساعت|hour|h|hr|روز|day|Day)', value, re.IGNORECASE)
                if match:
                    num = match.group(1)
                    unit = match.group(2)
                    if "روز" in unit or "day" in unit.lower():
                        battery_life = f"{num} روز"
                    else:
                        battery_life = f"{num} ساعت"
                else:
                    # اگر ساعت/روز نبود، میلی آمپر رو استخراج کن
                    mah_match = re.search(r'(\d+)\s*(میلی‌آمپر|mAh|MAH)', value, re.IGNORECASE)
                    if mah_match:
                        battery_life = f"{mah_match.group(1)} میلی‌آمپر"
                    else:
                        battery_life = value
                continue
            
            # ============ تشخیص نویز کنسلینگ ============
            if "نویز" in title or "کنسلینگ" in title or "حذف نویز" in title or "ANC" in title:
                if "دارد" in value or "فعال" in value or "بله" in value or "دارای" in value:
                    noise_canceling = "دارد"
                elif "ندارد" in value or "غیرفعال" in value or "خیر" in value or "بدون" in value:
                    noise_canceling = "ندارد"
                else:
                    noise_canceling = value
                continue
            
            # ============ تشخیص نسخه بلوتوث ============
            if "بلوتوث" in title or "Bluetooth" in title or "نسخه بلوتوث" in title:
                bt_match = re.search(r'(\d+\.?\d*)', value)
                if bt_match:
                    bluetooth_version = f"بلوتوث {bt_match.group(1)}"
                else:
                    bluetooth_version = value
                continue
    
    # ساخت رشته مشخصات هدفون (فقط اطلاعات مفید)
    specs_parts = []
    if headphone_type != "نامشخص":
        specs_parts.append(f"نوع: {headphone_type}")
    if battery_life != "نامشخص":
        specs_parts.append(f"باتری: {battery_life}")
    if noise_canceling != "نامشخص":
        specs_parts.append(f"نویز کنسلینگ: {noise_canceling}")
    if bluetooth_version != "نامشخص":
        specs_parts.append(f"اتصال: {bluetooth_version}")
    
    specs_string = " - ".join(specs_parts) if specs_parts else "مشخصات کامل نیست"
    desc_string = f"هدفون {headphone_type}" if headphone_type != "نامشخص" else "هدفون"
    if battery_life != "نامشخص":
        desc_string += f" با {battery_life} شارژ"
    
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


def scrape_digikala_phones(target_new_products=5, category_slug="mobile-phone", category_name="موبایل"):
    """
    دریافت محصولات دیجی‌کالا.
    target_new_products: تعداد محصولات جدیدی که می‌خواهیم در هر بار اجرا پیدا و اضافه کنیم.
    """
    # تنظیم لینک جستجو بر اساس دسته‌بندی
    search_url = f"https://api.digikala.com/v1/categories/{category_slug}/search/"
    
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
                short_title = clean_phone_name(original_title)

                # بررسی تکراری بودن بر اساس نام کوتاه شده
                if short_title in existing_names:
                    print(f"  [تکراری - رد شد] {short_title}")
                    continue

                print(f"  [محصول جدید یافت شد] در حال دریافت: {short_title}...")

                p_id = p.get("id")
                product_detail = get_phone_details(p_id)

                if product_detail:
                    specs, description = parse_specifications(product_detail)
                else:
                    specs, description = "نامشخص", "نامشخص"

                price_toman = get_best_price(p, product_detail)

                formatted_product = {
                    "id": product_id_counter,
                    "name": short_title,
                    "category": category_name,
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
    # اجرای استخراج موبایل‌ها
    print("--- شروع استخراج موبایل‌ها ---")
    scrape_digikala_phones(target_new_products=25, category_slug="mobile-phone", category_name="موبایل")
    
    # اجرای استخراج تبلت‌ها
    print("\n--- شروع استخراج تبلت‌ها ---")
    scrape_digikala_phones(target_new_products=25, category_slug="tablet", category_name="تبلت")
    
    # اجرای استخراج ساعت مچی (جایگزین هدفون)
    print("\n--- شروع استخراج ساعت مچی ---")
    scrape_digikala_phones(target_new_products=25, category_slug="wearable-gadget", category_name="ساعت هوشمند")