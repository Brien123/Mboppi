import implicit
import numpy as np
import pickle
from pathlib import Path
from scipy.sparse import csr_matrix
import logging

logger = logging.getLogger(__name__)


class CollaborativeFilteringModel:

    def __init__(self, factors=50, iterations=10):
        self.factors = factors
        self.iterations = iterations
        self.model = implicit.als.AlternatingLeastSquares(
            factors=factors,
            iterations=iterations,
            calculate_training_loss=False,
            num_threads=4,
            random_state=42,
            regularization=0.05
        )
        self.user_mapping = {}
        self.product_mapping = {}
        self.reverse_user_mapping = {}
        self.reverse_product_mapping = {}

    def train(self, user_product_pairs):
        logger.info(f"Starting training on {len(user_product_pairs)} interactions...")

        if len(user_product_pairs) < 10:
            logger.warning("Too few interactions to train model")
            return {"status": "failed", "reason": "insufficient_data"}

        users = list(set(u for u, _ in user_product_pairs))
        products = list(set(p for _, p in user_product_pairs))

        logger.info(f"Users: {len(users)}, Products: {len(products)}")

        self.user_mapping = {uid: idx for idx, uid in enumerate(users)}
        self.product_mapping = {pid: idx for idx, pid in enumerate(products)}
        self.reverse_user_mapping = {idx: uid for uid, idx in self.user_mapping.items()}
        self.reverse_product_mapping = {idx: pid for pid, idx in self.product_mapping.items()}

        rows = []
        cols = []
        data = []

        for user_id, product_id in user_product_pairs:
            if user_id in self.user_mapping and product_id in self.product_mapping:
                rows.append(self.user_mapping[user_id])
                cols.append(self.product_mapping[product_id])
                data.append(1)

        interaction_matrix = csr_matrix(
            (data, (rows, cols)),
            shape=(len(users), len(products))
        )

        logger.info("Training ALS model...")
        self.model.fit(interaction_matrix)
        logger.info("Training complete!")

        return {
            "status": "success",
            "users": len(users),
            "products": len(products),
            "interactions": len(user_product_pairs)
        }

    def get_recommendations(self, user_id, num_recommendations=20, exclude_ids=None):
        user_id_str = str(user_id)

        if user_id_str not in self.user_mapping:
            logger.debug(f"User {user_id_str} not in model")
            return []

        user_idx = self.user_mapping[user_id_str]
        user_factors = self.model.user_factors[user_idx]
        scores = self.model.item_factors.dot(user_factors)
        top_indices = np.argsort(-scores)[:num_recommendations * 3]

        recommendations = []
        exclude_ids = exclude_ids or set()
        exclude_ids = {str(pid) for pid in exclude_ids}

        for idx in top_indices:
            if idx in self.reverse_product_mapping:
                product_id = str(self.reverse_product_mapping[idx])
                if product_id not in exclude_ids:
                    recommendations.append(product_id)
                    if len(recommendations) >= num_recommendations:
                        break

        logger.debug(f"Generated {len(recommendations)} recommendations for {user_id_str}")
        return recommendations

    def save(self, filepath):
        try:
            filepath = Path(filepath)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'wb') as f:
                pickle.dump(self, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info(f"Model saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            return False

    @staticmethod
    def load(filepath):
        try:
            filepath = Path(filepath)
            if not filepath.exists():
                logger.warning(f"Model file not found: {filepath}")
                return None
            with open(filepath, 'rb') as f:
                model = pickle.load(f)
            logger.info(f"Model loaded from {filepath}")
            return model
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return None

    def get_similar_products(self, product_id, num_similar=10):
        product_id_str = str(product_id)

        if product_id_str not in self.product_mapping:
            logger.debug(f"Product {product_id_str} not in model")
            return []

        product_idx = self.product_mapping[product_id_str]
        product_factors = self.model.item_factors[product_idx]
        scores = self.model.item_factors.dot(product_factors)
        top_indices = np.argsort(-scores)[1:num_similar + 1]

        similar = [
            str(self.reverse_product_mapping[idx])
            for idx in top_indices
            if idx in self.reverse_product_mapping
        ]

        return similar

    def get_model_stats(self):
        return {
            "factors": self.factors,
            "iterations": self.iterations,
            "num_users": len(self.user_mapping),
            "num_products": len(self.product_mapping),
            "user_factors_shape": self.model.user_factors.shape,
            "item_factors_shape": self.model.item_factors.shape,
        }
