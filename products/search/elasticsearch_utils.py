import os

from ..models import Product
from .models import PRODUCT_INDEX_MAPPING
from core.elasticsearch_client import ElasticsearchClient
from elasticsearch import helpers
from elasticsearch.helpers import BulkIndexError
from typing import List
import logging

class ElasticsearchUtils:
    def __init__(self):
        self.client = ElasticsearchClient().client

    def create_index(self, index_name: str, mapping: dict)->bool:
        if not self.client.indices.exists(index=index_name):
            self.client.indices.create(index=index_name, body=mapping)
            return True
        return False
    
    def delete_index(self, index_name: str)->bool:
        if self.client.indices.exists(index=index_name):
            self.client.indices.delete(index=index_name)
            return True
        return False
    
    def index_data(self, index_name: str, document: dict)->bool:
        try:
            self.client.index(index=index_name, document=document, id=document["id"])
            return True
        except Exception as e:
            logging.error(f"Error indexing document: {e}")
            return False
        
    def index_exists(self, index_name: str)->bool:
        return self.client.indices.exists(index=index_name)
        
    def update_data(self, index_name: str, document_id: str, document: dict)->bool:
        try:
            self.client.update(index=index_name, id=document_id, body={"doc": document})
            return True
        except Exception as e:
            logging.error(f"Error updating document: {e}")
            return False
        
    def delete_index_data(self, index_name: str, document_id: str)->bool:
        try:
            self.client.delete(index=index_name, id=document_id)
            return True
        except Exception as e:
            logging.error(f"Error deleting document: {e}")
            return False
        
    def bulk_index_data(self, index_name: str, products: List[Product])->bool:
        actions = []
        for product in products:
            document = self.convert_product_to_document(product)
            actions.append({
                "_index": index_name,
                "_id": document["id"],
                "_source": document
            })
        
        try:
            helpers.bulk(self.client, actions)
            return True
        except BulkIndexError as e:
            logging.error(f"Bulk indexing error: {e}")
            return False
    
    def convert_product_to_document(self, product: Product):
        """
        Converts a Django Product model instance into an Elasticsearch document
        with CLIP text and image features.
        """
        from .feature_extraction import CLIPFeatureExtractor
        extractor = CLIPFeatureExtractor()

        text_content = f"{product.name}. {product.description}"
        text_features = extractor.encode_text(text_content)

        image_features = []
        first_image = product.product_images.first()
        
        if first_image and first_image.image_large:
            try:
                if os.path.exists(first_image.image_large.path):
                    image_features = extractor.encode_image(first_image.image_large.path)
                else:
                    image_features = extractor.encode_image(first_image.image_large.url)
            except Exception as e:
                logging.error(f"Vector encoding failed for product {product.id}: {e}")

        doc = {
            "id": str(product.id),
            "name": product.name,
            "slug": product.slug,
            "description": product.description,
            "category": {
                "id": str(product.category.id),
                "name": product.category.name,
                "slug": product.category.slug,
            },
            "base_price": float(product.base_price),
            "stock": product.stock,
            "is_active": product.is_active,
            "created_at": product.created_at.isoformat(),
            "updated_at": product.updated_at.isoformat(),
            "images": [
                {"image_large": img.image_large.url if img.image_large else None}
                for img in product.product_images.all()
            ],
            "suggest": {"input": [product.name, product.category.name]},
        }

        if text_features:
            doc["text_features"] = text_features
        if image_features:
            doc["image_features"] = image_features

        return doc

    def create_product_index(self):
        index_name = "slash_products"
        if not self.client.indices.exists(index=index_name):
            self.client.indices.create(index=index_name, body=PRODUCT_INDEX_MAPPING)
            return f"Index {index_name} created."
        return f"Index {index_name} already exists."
    
    def product_search(self, query: str, index_name: str = "slash_products", size: int=10, page: int=1, sort: str = "relevance", min_price: float=None, max_price: float=None, category_slug: str=None):
        search_query = {
            "query": {
                "bool": {
                    "must": [],
                    "filter": [{"term": {"is_active": True}}]
                }
            },
            "from": (page - 1) * size,
            "size": size
        }

        # Full-text Search
        if query:
            search_query["query"]["bool"]["must"].append({
                "multi_match": {
                    "query": query,
                    "fields": ["name^3", "name.suggest", "description", "category.name"],
                    "type": "best_fields",
                    "fuzziness": "AUTO",
                    "prefix_length": 2,
                    "max_expansions": 50
                }
            })
        else:
            search_query["query"]["bool"]["must"].append({"match_all": {}})

        # Price Filtering
        if min_price is not None or max_price is not None:
            price_range = {"range": {"base_price": {}}}
            if min_price is not None: price_range["range"]["base_price"]["gte"] = min_price
            if max_price is not None: price_range["range"]["base_price"]["lte"] = max_price
            search_query["query"]["bool"]["filter"].append(price_range)

        if category_slug:
            search_query["query"]["bool"]["filter"].append({"term": {"category.slug": category_slug}})

        # Sorting
        sort_map = {
            "price_asc": [{"base_price": "asc"}],
            "price_desc": [{"base_price": "desc"}],
            "newest": [{"created_at": "desc"}],
            "relevance": ["_score"]
        }
        search_query["sort"] = sort_map.get(sort, ["_score"])

        try:
            return self.client.search(index=index_name, body=search_query)
        except Exception as e:
            logging.error(f"ES Search Error: {e}")
            return None
    
    def get_suggestions(self, query: str, index_name: str = "slash_products", size: int = 5):
        if not query:
            return []

        search_query = {
            "_source": ["id", "name", "slug"],
            "suggest": {
                "product-suggestions": {
                    "prefix": query,
                    "completion": {
                        "field": "suggest",
                        "size": size,
                        "fuzzy": {
                            "fuzziness": "AUTO"
                        },
                        "skip_duplicates": True
                    }
                }
            }
        }

        try:
            response = self.client.search(index=index_name, body=search_query)
            options = response['suggest']['product-suggestions'][0]['options']
            
            return [
                {
                    "id": opt['_source']['id'],
                    "name": opt['_source']['name'],
                    "slug": opt['_source']['slug']
                } 
                for opt in options
            ]
        except Exception as e:
            logging.error(f"ES Suggestion Error: {e}")
            return []
        
    def get_similar_products(self, product_id: str, index_name: str = "slash_products", size: int = 10, page: int = 1):
            """
            Finds similar products using a script_score for Cosine Similarity.
            """
            try:
                source_doc = self.client.get(index=index_name, id=str(product_id))
                target_vector = source_doc['_source'].get('text_features')
                
                if not target_vector or len(target_vector) != 512:
                    return None
            except Exception as e:
                logging.error(f"ES Similarity Search Error: {e}")
                return None

            search_query = {
                "size": size,
                "from": (page - 1) * size,
                "min_score": 1,
                "query": {
                    "bool": {
                        "must": [
                            {
                                "script_score": {
                                    "query": {"match_all": {}},
                                    "script": {
                                        "source": """
                                            if (doc[params.field].size() == 0) {
                                                return 0.0;
                                            }
                                            return cosineSimilarity(params.target_vector, params.field) + 1.0;
                                        """,
                                        "params": {
                                            "target_vector": target_vector,
                                            "field": "text_features"
                                        }
                                    }
                                }
                            }
                        ],
                        "must_not": [
                            {"term": {"id": product_id}}
                        ],
                        "filter": [
                            {"term": {"is_active": True}}
                        ]
                    }
                },
                "_source": False
            }

            try:
                logging.info(f"Executing ES Similarity Search for product_id={product_id}, page={page}, size={size}")
                return self.client.search(index=index_name, body=search_query)
            except Exception as e:
                logging.error(f"ES Script Score Error: {e}")
                return None
            
    def search_by_image(self, query_vector: list, index_name: str = "slash_products", size: int = 10, page: int = 1):
        """
        Finds products visually similar to the provided vector using Cosine Similarity.
        """
        search_query = {
            "size": size,
            "from": (page - 1) * size,
            "min_score": 1.8,
            "query": {
                "script_score": {
                    "query": {
                        "bool": {
                            "filter": [{"term": {"is_active": True}}]
                        }
                    },
                    "script": {
                        "source": """
                            // Simplified syntax to prevent compile errors
                            if (doc[params.field].size() > 0) {
                                return cosineSimilarity(params.target_vector, params.field) + 1.0;
                            } else {
                                return 0.0;
                            }
                        """,
                        "params": {
                            "target_vector": query_vector,
                            "field": "image_features"
                        }
                    }
                }
            },
            "_source": False
        }

        try:
            return self.client.search(index=index_name, body=search_query)
        except Exception as e:
            logging.error(f"Image Search ES Error: {e}")
            return None