PRODUCT_INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "suggest": {"type": "completion"}, # For autocomplete
            "name": {
                "type": "text",
                "analyzer": "standard",
                "fields": {
                    "suggest": {"type": "search_as_you_type"}, # For autocomplete
                    "raw": {"type": "keyword"}                # For exact sorting
                }
            },
            "slug": {"type": "keyword"},
            "description": {"type": "text", "analyzer": "english"},
            "category": {
                "properties": {
                    "id": {"type": "keyword"},
                    "name": {"type": "text", "fields": {"raw": {"type": "keyword"}}},
                    "slug": {"type": "keyword"}
                }
            },
            "base_price": {"type": "double"},
            "stock": {"type": "integer"},
            "is_active": {"type": "boolean"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
            "images": {
                "properties": {
                    "image_thumb": {"type": "keyword", "index": False}
                }
            },
            "text_features": {
                "type": "dense_vector",
                "dims": 512,
                "index": True,
                "similarity": "cosine"
            },
            "image_features": {
                "type": "dense_vector",
                "dims": 512,
                "index": True,
                "similarity": "cosine"
            },
        }
    }
}