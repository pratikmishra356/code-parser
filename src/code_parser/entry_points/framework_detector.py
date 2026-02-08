"""Framework detection based on imports and dependencies."""

from typing import Dict, Set

from code_parser.core import Language


class FrameworkDetector:
    """Detects frameworks used in code based on imports and patterns."""

    # Framework detection patterns
    PYTHON_FRAMEWORKS: Dict[str, Set[str]] = {
        "flask": {"flask", "Flask"},
        "fastapi": {"fastapi", "FastAPI"},
        "django": {"django", "Django"},
        "celery": {"celery", "Celery"},
        "kafka": {"kafka", "confluent_kafka", "aiokafka"},
        "pulsar": {"pulsar", "pulsar_client"},
        "apscheduler": {"apscheduler", "APScheduler"},
    }

    JAVA_FRAMEWORKS: Dict[str, Set[str]] = {
        "spring-boot": {"org.springframework", "org.springframework.boot"},
        "jax-rs": {"javax.ws.rs", "jakarta.ws.rs"},
        "grpc": {"io.grpc", "com.google.protobuf"},
        "kafka": {"org.apache.kafka"},
        "rabbitmq": {"org.springframework.amqp", "com.rabbitmq"},
    }

    KOTLIN_FRAMEWORKS: Dict[str, Set[str]] = {
        "spring-boot": {"org.springframework", "org.springframework.boot"},
        "ktor": {"io.ktor"},
        "apache-camel": {"org.apache.camel"},
        "kafka": {"org.apache.kafka"},
    }

    JAVASCRIPT_FRAMEWORKS: Dict[str, Set[str]] = {
        "express": {"express"},
        "nextjs": {"next"},
        "aws-lambda": {"aws-lambda", "@aws-sdk"},
        "kafka": {"kafkajs", "node-rdkafka"},
    }

    RUST_FRAMEWORKS: Dict[str, Set[str]] = {
        "actix": {"actix-web", "actix"},
        "rocket": {"rocket"},
        "tokio": {"tokio"},
    }

    @classmethod
    def detect_frameworks(cls, language: Language, imports: Set[str]) -> Set[str]:
        """
        Detect frameworks from imports.
        
        Args:
            language: Programming language
            imports: Set of import/module names
            
        Returns:
            Set of detected framework names
        """
        frameworks: Set[str] = set()

        if language == Language.PYTHON:
            framework_map = cls.PYTHON_FRAMEWORKS
        elif language == Language.JAVA:
            framework_map = cls.JAVA_FRAMEWORKS
        elif language == Language.KOTLIN:
            framework_map = cls.KOTLIN_FRAMEWORKS
        elif language == Language.JAVASCRIPT:
            framework_map = cls.JAVASCRIPT_FRAMEWORKS
        elif language == Language.RUST:
            framework_map = cls.RUST_FRAMEWORKS
        else:
            return frameworks

        # Check each import against framework patterns
        for import_name in imports:
            for framework, patterns in framework_map.items():
                for pattern in patterns:
                    if pattern.lower() in import_name.lower():
                        frameworks.add(framework)
                        break

        return frameworks

    @classmethod
    def get_entry_point_queries_for_frameworks(
        cls, language: Language, frameworks: Set[str]
    ) -> Set[str]:
        """
        Get relevant query pattern names for detected frameworks.
        
        Args:
            language: Programming language
            frameworks: Set of detected framework names
            
        Returns:
            Set of query pattern names to use
        """
        # Map frameworks to query patterns
        query_map: Dict[str, Set[str]] = {}

        if language == Language.PYTHON:
            query_map = {
                "flask": {"flask_route", "flask_blueprint_route"},
                "fastapi": {"fastapi_route", "fastapi_router", "fastapi_websocket"},
                "django": {"django_api_view", "django_viewset_action"},
                "celery": {"celery_task"},
                "kafka": {"kafka_consumer"},
                "pulsar": {"pulsar_subscribe"},
                "apscheduler": {"apscheduler", "scheduled_decorator", "cron_decorator"},
            }
        elif language == Language.JAVA:
            query_map = {
                "spring-boot": {"spring_rest_controller", "spring_request_mapping"},
                "kafka": {"kafka_listener"},
                "scheduler": {"scheduled_annotation"},
            }
        elif language == Language.KOTLIN:
            query_map = {
                "spring-boot": {"spring_rest_controller", "spring_request_mapping", "spring_scheduled"},
                "ktor": {"ktor_routing", "ktor_route"},
                "apache-camel": {"camel_route_builder_class", "camel_configure_method", "camel_from_call"},
                "kafka": {"kafka_listener"},
                "pulsar": {"pulsar_consumer"},
            }
        elif language == Language.JAVASCRIPT:
            query_map = {
                "express": {"express_route"},
                "nextjs": {"nextjs_api_route"},
                "aws-lambda": {"lambda_handler"},
            }
        elif language == Language.RUST:
            query_map = {
                "actix": {"actix_get", "actix_post"},
                "rocket": {"rocket_get"},
            }
        else:
            query_map = {}

        queries: Set[str] = set()
        for framework in frameworks:
            if framework in query_map:
                queries.update(query_map[framework])

        return queries
