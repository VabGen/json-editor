# dataset = load_dataset("amazon_reviews_multi", "en")   # Загрузка датасета
#
# books = dataset.filter(lambda x: x["product_category"] == "book")   # Фильтрация (например, только книги)
#
# inputs = tokenizer(examples["review_body"], max_length=512, truncation=True)  # Токенизация
# labels = tokenizer(examples["review_title"], max_length=30, truncation=True)
