# kb_manager.py - Jena Fuseki integration for bookshelf KB

import requests
import json
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class KBDesign:
    """Bookshelf design for KB storage"""
    design_id: str
    width: float
    height: float
    depth: float
    thickness: float
    add_top: bool
    material: str
    shelf_positions: List[float]
    divider_positions: List[float]
    total_cost: float
    max_load: float
    generated_by: str  # KB_SEARCH, GA_OPTIMIZED, or MANUAL
    created_date: str
    popularity_score: int = 0
    components_used: List[str] = field(default_factory=list)


@dataclass
class KBComponent:
    """Inventory component stored in the KB"""
    component_id: str
    component_type: str
    width: float
    height: float
    depth: float
    thickness: float
    material: str
    joint_pattern: str
    stock_quantity: int = 0
    status: str = "available"  # available, reserved, pending_fabrication
    last_used: Optional[str] = None


class FusekiKBManager:
    """
    Manager for Jena Fuseki knowledge base operations.
    Handles storage, retrieval, and querying of bookshelf designs.
    """
    
    def __init__(self, fuseki_url: str = "http://localhost:3030"):
        """
        Initialize connection to Fuseki server.
        
        Args:
            fuseki_url: Base URL of Fuseki server
        """
        self.base_url = fuseki_url
        self.dataset = "bookshelf_kb"
        self.sparql_endpoint = f"{fuseki_url}/{self.dataset}/sparql"
        self.update_endpoint = f"{fuseki_url}/{self.dataset}/update"
        self.data_endpoint = f"{fuseki_url}/{self.dataset}/data"
        
        # Prefixes for SPARQL queries
        self.prefixes = """
        PREFIX : <http://example.org/bookshelf#>
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        """
    
    def test_connection(self) -> bool:
        """Test if Fuseki server is reachable"""
        try:
            response = requests.get(f"{self.base_url}/$/ping")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to connect to Fuseki: {e}")
            return False
    
    def create_dataset(self) -> bool:
        """Create dataset if it doesn't exist"""
        try:
            # Check if dataset exists
            response = requests.get(f"{self.base_url}/$/datasets/{self.dataset}")
            if response.status_code == 200:
                logger.info(f"Dataset '{self.dataset}' already exists")
                return True
            
            # Create new dataset
            data = {
                "dbName": self.dataset,
                "dbType": "tdb2"
            }
            response = requests.post(f"{self.base_url}/$/datasets", data=data)
            
            if response.status_code in [200, 201]:
                logger.info(f"Dataset '{self.dataset}' created successfully")
                return True
            else:
                logger.error(f"Failed to create dataset: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating dataset: {e}")
            return False
    
    def store_design(self, design: KBDesign) -> bool:
        """
        Store a bookshelf design in the KB.
        
        Args:
            design: KBDesign object to store
            
        Returns:
            Success status
        """
        try:
            # Build RDF triples for the design
            triples = self._design_to_triples(design)
            
            # SPARQL INSERT query
            query = f"""
            {self.prefixes}
            INSERT DATA {{
                {triples}
            }}
            """
            
            response = requests.post(
                self.update_endpoint,
                data={"update": query},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code in [200, 204]:
                logger.info(f"Design {design.design_id} stored successfully")
                return True
            else:
                logger.error(f"Failed to store design: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error storing design: {e}")
            return False

    def store_component(self, component: KBComponent) -> bool:
        """Store or update a component in the KB inventory."""
        try:
            triples = self._component_to_triples(component)
            query = f"""
            {self.prefixes}
            INSERT DATA {{
                {triples}
            }}
            """
            response = requests.post(
                self.update_endpoint,
                data={"update": query},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            if response.status_code in [200, 204]:
                logger.info(f"Component {component.component_id} stored successfully")
                return True
            else:
                logger.error(f"Failed to store component: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error storing component: {e}")
            return False

    def list_components(self, component_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all components (optionally filtered by type)."""
        filter_clause = ""
        if component_type:
            filter_clause = f'FILTER(?type = "{component_type}")'

        query = f"""
        {self.prefixes}
        SELECT ?id ?type ?width ?height ?depth ?thickness ?material ?stock ?status ?joint ?lastUsed
        WHERE {{
            ?comp rdf:type :Component ;
                  :componentID ?id ;
                  :componentType ?type ;
                  :componentWidth ?width ;
                  :componentHeight ?height ;
                  :componentDepth ?depth ;
                  :componentThickness ?thickness ;
                  :componentMaterial ?material ;
                  :stockQuantity ?stock ;
                  :componentStatus ?status .
            OPTIONAL {{ ?comp :jointPattern ?joint . }}
            OPTIONAL {{ ?comp :lastUsed ?lastUsed . }}
            {filter_clause}
        }}
        ORDER BY DESC(?stock)
        """
        try:
            response = requests.post(
                self.sparql_endpoint,
                data={"query": query},
                headers={"Accept": "application/sparql-results+json"}
            )
            if response.status_code == 200:
                results = response.json()
                items = []
                for b in results.get("results", {}).get("bindings", []):
                    items.append({
                        "component_id": b["id"]["value"],
                        "component_type": b["type"]["value"],
                        "width": float(b["width"]["value"]),
                        "height": float(b["height"]["value"]),
                        "depth": float(b["depth"]["value"]),
                        "thickness": float(b["thickness"]["value"]),
                        "material": b["material"]["value"],
                        "stock": int(b["stock"]["value"]),
                        "status": b["status"]["value"],
                        "joint_pattern": b.get("joint", {}).get("value"),
                        "last_used": b.get("lastUsed", {}).get("value")
                    })
                return items
            logger.error(f"Component list query failed: {response.text}")
            return []
        except Exception as e:
            logger.error(f"Error listing components: {e}")
            return []

    def find_components(self, component_type: str, material: str,
                        width: float, height: float, depth: float,
                        thickness: float, tolerance: float = 5.0,
                        limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find stocked components that match the dimensional requirements.
        Tolerance is in millimeters.
        """
        w_min, w_max = width - tolerance, width + tolerance
        h_min, h_max = height - tolerance, height + tolerance
        d_min, d_max = depth - tolerance, depth + tolerance
        t_min, t_max = thickness - tolerance, thickness + tolerance

        query = f"""
        {self.prefixes}
        SELECT ?comp ?id ?stock ?status ?width ?height ?depth ?thickness ?joint
        WHERE {{
            ?comp rdf:type :Component ;
                  :componentID ?id ;
                  :componentType "{component_type}" ;
                  :componentMaterial "{material}" ;
                  :componentWidth ?width ;
                  :componentHeight ?height ;
                  :componentDepth ?depth ;
                  :componentThickness ?thickness ;
                  :stockQuantity ?stock ;
                  :componentStatus ?status .
            OPTIONAL {{ ?comp :jointPattern ?joint . }}
            FILTER(?stock > 0)
            FILTER(?width >= {w_min} && ?width <= {w_max})
            FILTER(?height >= {h_min} && ?height <= {h_max})
            FILTER(?depth >= {d_min} && ?depth <= {d_max})
            FILTER(?thickness >= {t_min} && ?thickness <= {t_max})
        }}
        ORDER BY ASC(ABS(?width - {width}) + ABS(?height - {height}) + ABS(?thickness - {thickness}))
        LIMIT {limit}
        """

        try:
            response = requests.post(
                self.sparql_endpoint,
                data={"query": query},
                headers={"Accept": "application/sparql-results+json"}
            )
            if response.status_code == 200:
                results = response.json()
                matches = []
                for b in results.get("results", {}).get("bindings", []):
                    matches.append({
                        "component_id": b["id"]["value"],
                        "stock": int(b["stock"]["value"]),
                        "status": b["status"]["value"],
                        "width": float(b["width"]["value"]),
                        "height": float(b["height"]["value"]),
                        "depth": float(b["depth"]["value"]),
                        "thickness": float(b["thickness"]["value"]),
                        "joint_pattern": b.get("joint", {}).get("value")
                    })
                return matches
            logger.error(f"Component search failed: {response.text}")
            return []
        except Exception as e:
            logger.error(f"Error searching components: {e}")
            return []

    def reserve_component(self, component_id: str, quantity: int = 1) -> bool:
        """Decrement stock for a component and update last-used timestamp."""
        try:
            now = datetime.now().isoformat()
            query = f"""
            {self.prefixes}
            DELETE {{
                ?comp :stockQuantity ?oldStock .
            }}
            INSERT {{
                ?comp :stockQuantity ?newStock ;
                      :lastUsed "{now}"^^xsd:dateTime ;
                      :componentStatus "reserved" .
            }}
            WHERE {{
                ?comp :componentID "{component_id}" ;
                      :stockQuantity ?oldStock .
                BIND(IF(?oldStock - {quantity} < 0, 0, ?oldStock - {quantity}) AS ?newStock)
            }}
            """
            response = requests.post(
                self.update_endpoint,
                data={"update": query},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            return response.status_code in [200, 204]
        except Exception as e:
            logger.error(f"Error reserving component {component_id}: {e}")
            return False

    def allocate_components(self, requests_spec: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Allocate components for a design. Returns list of allocations with status
        'reused' or 'missing'. Missing components should later be created via GA.
        """
        allocations: List[Dict[str, Any]] = []
        if not requests_spec:
            return allocations

        for spec in requests_spec:
            quantity = int(spec.get("quantity", 1))
            for _ in range(quantity):
                matches = self.find_components(
                    component_type=spec["component_type"],
                    material=spec["material"],
                    width=spec["width"],
                    height=spec["height"],
                    depth=spec["depth"],
                    thickness=spec["thickness"],
                    tolerance=spec.get("tolerance_mm", 3.0),
                    limit=1
                )
                if matches:
                    comp = matches[0]
                    self.reserve_component(comp["component_id"])
                    allocations.append({
                        "status": "reused",
                        "component_id": comp["component_id"],
                        "component_type": spec["component_type"],
                        "material": spec["material"],
                        "width": comp["width"],
                        "height": comp["height"],
                        "depth": comp["depth"],
                        "thickness": comp["thickness"],
                        "description": spec.get("description", spec["component_type"]),
                        "joint_pattern": spec.get("joint_pattern")
                    })
                else:
                    new_id = f"COMP-{uuid.uuid4().hex[:6]}"
                    allocations.append({
                        "status": "missing",
                        "component_id": new_id,
                        "component_type": spec["component_type"],
                        "material": spec["material"],
                        "width": spec["width"],
                        "height": spec["height"],
                        "depth": spec["depth"],
                        "thickness": spec["thickness"],
                        "description": spec.get("description", spec["component_type"]),
                        "joint_pattern": spec.get("joint_pattern")
                    })
        return allocations
    
    def search_similar_designs(self, width: float, height: float, depth: float,
                              tolerance: float = 0.1) -> List[Dict[str, Any]]:
        """
        Search for similar designs in the KB.
        
        Args:
            width, height, depth: Target dimensions
            tolerance: Relative tolerance for matching (0.1 = 10%)
            
        Returns:
            List of matching designs
        """
        w_min = width * (1 - tolerance)
        w_max = width * (1 + tolerance)
        h_min = height * (1 - tolerance)
        h_max = height * (1 + tolerance)
        d_min = depth * (1 - tolerance)
        d_max = depth * (1 + tolerance)
        
        query = f"""
        {self.prefixes}
        SELECT ?design ?id ?width ?height ?depth ?thickness ?material 
               ?cost ?load ?popularity ?generated_by
        WHERE {{
            ?design rdf:type :BookshelfDesign ;
                    :designID ?id ;
                    :hasWidth ?width ;
                    :hasHeight ?height ;
                    :hasDepth ?depth ;
                    :hasThickness ?thickness ;
                    :hasMaterial ?material ;
                    :totalCost ?cost ;
                    :maxLoad ?load ;
                    :popularityScore ?popularity ;
                    :generatedBy ?generated_by .
            
            FILTER(?width >= {w_min} && ?width <= {w_max})
            FILTER(?height >= {h_min} && ?height <= {h_max})
            FILTER(?depth >= {d_min} && ?depth <= {d_max})
        }}
        ORDER BY DESC(?popularity)
        LIMIT 10
        """
        
        try:
            response = requests.post(
                self.sparql_endpoint,
                data={"query": query},
                headers={"Accept": "application/sparql-results+json"}
            )
            
            if response.status_code == 200:
                results = response.json()
                designs = []
                for binding in results.get("results", {}).get("bindings", []):
                    designs.append({
                        "design_id": binding["id"]["value"],
                        "width": float(binding["width"]["value"]),
                        "height": float(binding["height"]["value"]),
                        "depth": float(binding["depth"]["value"]),
                        "thickness": float(binding["thickness"]["value"]),
                        "material": binding["material"]["value"],
                        "cost": float(binding["cost"]["value"]),
                        "max_load": float(binding["load"]["value"]),
                        "popularity": int(binding["popularity"]["value"]),
                        "generated_by": binding["generated_by"]["value"]
                    })
                return designs
            else:
                logger.error(f"Search query failed: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error searching designs: {e}")
            return []
    
    def get_design_details(self, design_id: str) -> Optional[KBDesign]:
        """
        Retrieve full details of a specific design.
        
        Args:
            design_id: Unique design identifier
            
        Returns:
            KBDesign object or None if not found
        """
        query = f"""
        {self.prefixes}
        SELECT ?width ?height ?depth ?thickness ?addTop ?material
               ?cost ?load ?generated_by ?created ?popularity
               (GROUP_CONCAT(DISTINCT ?shelf_z; SEPARATOR=",") AS ?shelves)
               (GROUP_CONCAT(DISTINCT ?div_x; SEPARATOR=",") AS ?dividers)
        WHERE {{
            ?design :designID "{design_id}" ;
                    :hasWidth ?width ;
                    :hasHeight ?height ;
                    :hasDepth ?depth ;
                    :hasThickness ?thickness ;
                    :hasTopPanel ?addTop ;
                    :hasMaterial ?material ;
                    :totalCost ?cost ;
                    :maxLoad ?load ;
                    :generatedBy ?generated_by ;
                    :createdDate ?created ;
                    :popularityScore ?popularity .
            
            OPTIONAL {{
                ?design :hasComponent ?shelf .
                ?shelf rdf:type :Shelf ;
                       :atPosition ?shelf_z .
            }}
            
            OPTIONAL {{
                ?design :hasComponent ?divider .
                ?divider rdf:type :Divider ;
                         :atPosition ?div_x .
            }}
        }}
        GROUP BY ?width ?height ?depth ?thickness ?addTop ?material
                 ?cost ?load ?generated_by ?created ?popularity
        """
        
        try:
            response = requests.post(
                self.sparql_endpoint,
                data={"query": query},
                headers={"Accept": "application/sparql-results+json"}
            )
            
            if response.status_code == 200:
                results = response.json()
                bindings = results.get("results", {}).get("bindings", [])
                
                if not bindings:
                    return None
                
                b = bindings[0]
                
                # Parse shelf and divider positions
                shelves = []
                if "shelves" in b and b["shelves"]["value"]:
                    shelves = [float(x) for x in b["shelves"]["value"].split(",") if x]
                
                dividers = []
                if "dividers" in b and b["dividers"]["value"]:
                    dividers = [float(x) for x in b["dividers"]["value"].split(",") if x]
                
                return KBDesign(
                    design_id=design_id,
                    width=float(b["width"]["value"]),
                    height=float(b["height"]["value"]),
                    depth=float(b["depth"]["value"]),
                    thickness=float(b["thickness"]["value"]),
                    add_top=b["addTop"]["value"].lower() == "true",
                    material=b["material"]["value"],
                    shelf_positions=shelves,
                    divider_positions=dividers,
                    total_cost=float(b["cost"]["value"]),
                    max_load=float(b["load"]["value"]),
                    generated_by=b["generated_by"]["value"],
                    created_date=b["created"]["value"],
                    popularity_score=int(b["popularity"]["value"])
                )
                
        except Exception as e:
            logger.error(f"Error retrieving design {design_id}: {e}")
            return None
    
    def record_order(self, customer_name: str, design_id: str, quantity: int = 1) -> str:
        """
        Record a customer order and update design popularity.
        
        Args:
            customer_name: Customer name
            design_id: Design being ordered
            quantity: Number of units
            
        Returns:
            Customer ID string
        """
        customer_id = f"CUST-{uuid.uuid4().hex[:6]}"
        order_id = f"ORD-{uuid.uuid4().hex[:8]}"
        order_date = datetime.now().isoformat()
        
        # Insert order and update popularity in one transaction
        query = f"""
        {self.prefixes}
        INSERT {{
            :customer_{customer_id} rdf:type :Customer ;
                                    :customerID "{customer_id}" ;
                                    :customerName "{customer_name}" .
            
            :order_{order_id} rdf:type :Order ;
                             :orderID "{order_id}" ;
                             :orderedBy :customer_{customer_id} ;
                             :orderedDesign ?design ;
                             :orderDate "{order_date}"^^xsd:dateTime ;
                             :quantity {quantity} .
        }}
        WHERE {{
            ?design :designID "{design_id}" .
        }} ;
        
        DELETE {{
            ?design :popularityScore ?oldScore .
        }}
        INSERT {{
            ?design :popularityScore ?newScore .
        }}
        WHERE {{
            ?design :designID "{design_id}" ;
                    :popularityScore ?oldScore .
            BIND(?oldScore + {quantity} AS ?newScore)
        }}
        """
        
        try:
            response = requests.post(
                self.update_endpoint,
                data={"update": query},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code in [200, 204]:
                logger.info(f"Order {order_id} recorded for design {design_id}")
                return customer_id  # Return customer ID as expected by web_app
            else:
                logger.error(f"Failed to record order: {response.text}")
                return customer_id  # Still return customer ID even if KB update fails
                
        except Exception as e:
            logger.error(f"Error recording order: {e}")
            return customer_id  # Still return customer ID even if KB fails
    
    def get_popular_designs(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get most popular designs by order count"""
        query = f"""
        {self.prefixes}
        SELECT ?id ?width ?height ?depth ?material ?cost ?popularity
        WHERE {{
            ?design rdf:type :BookshelfDesign ;
                    :designID ?id ;
                    :hasWidth ?width ;
                    :hasHeight ?height ;
                    :hasDepth ?depth ;
                    :hasMaterial ?material ;
                    :totalCost ?cost ;
                    :popularityScore ?popularity .
        }}
        ORDER BY DESC(?popularity)
        LIMIT {limit}
        """
        
        try:
            response = requests.post(
                self.sparql_endpoint,
                data={"query": query},
                headers={"Accept": "application/sparql-results+json"}
            )
            
            if response.status_code == 200:
                results = response.json()
                designs = []
                for binding in results.get("results", {}).get("bindings", []):
                    designs.append({
                        "design_id": binding["id"]["value"],
                        "width": float(binding["width"]["value"]),
                        "height": float(binding["height"]["value"]),
                        "depth": float(binding["depth"]["value"]),
                        "material": binding["material"]["value"],
                        "cost": float(binding["cost"]["value"]),
                        "popularity": int(binding["popularity"]["value"])
                    })
                return designs
                
        except Exception as e:
            logger.error(f"Error getting popular designs: {e}")
            return []
    
    def get_customer_orders(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get all orders for a specific customer"""
        query = f"""
        {self.prefixes}
        SELECT ?order_id ?design_id ?quantity ?date ?width ?height ?depth ?cost
        WHERE {{
            ?order :orderedBy ?customer ;
                   :orderID ?order_id ;
                   :orderedDesign ?design ;
                   :quantity ?quantity ;
                   :orderDate ?date .
            
            ?customer :customerID "{customer_id}" .
            
            ?design :designID ?design_id ;
                    :hasWidth ?width ;
                    :hasHeight ?height ;
                    :hasDepth ?depth ;
                    :totalCost ?cost .
        }}
        ORDER BY DESC(?date)
        """
        
        try:
            response = requests.post(
                self.sparql_endpoint,
                data={"query": query},
                headers={"Accept": "application/sparql-results+json"}
            )
            
            if response.status_code == 200:
                results = response.json()
                orders = []
                for binding in results.get("results", {}).get("bindings", []):
                    orders.append({
                        "order_id": binding["order_id"]["value"],
                        "design_id": binding["design_id"]["value"],
                        "quantity": int(binding["quantity"]["value"]),
                        "date": binding["date"]["value"],
                        "dimensions": {
                            "width": float(binding["width"]["value"]),
                            "height": float(binding["height"]["value"]),
                            "depth": float(binding["depth"]["value"])
                        },
                        "cost": float(binding["cost"]["value"])
                    })
                return orders
                
        except Exception as e:
            logger.error(f"Error getting customer orders: {e}")
            return []
    
    def _design_to_triples(self, design: KBDesign) -> str:
        """Convert KBDesign to RDF triples"""
        design_uri = f":design_{design.design_id}"
        
        triples = f"""
        {design_uri} rdf:type :BookshelfDesign ;
                     :designID "{design.design_id}" ;
                     :hasWidth {design.width} ;
                     :hasHeight {design.height} ;
                     :hasDepth {design.depth} ;
                     :hasThickness {design.thickness} ;
                     :hasTopPanel {str(design.add_top).lower()} ;
                     :hasMaterial "{design.material}" ;
                     :totalCost {design.total_cost} ;
                     :maxLoad {design.max_load} ;
                     :generatedBy "{design.generated_by}" ;
                     :createdDate "{design.created_date}"^^xsd:dateTime ;
                     :popularityScore {design.popularity_score} .
        """
        
        # Add shelf components
        for i, z_pos in enumerate(design.shelf_positions):
            shelf_uri = f":shelf_{design.design_id}_{i}"
            triples += f"""
            {shelf_uri} rdf:type :Shelf ;
                        :atPosition {z_pos} .
            {design_uri} :hasComponent {shelf_uri} .
            """
        
        # Add divider components
        for i, x_pos in enumerate(design.divider_positions):
            div_uri = f":divider_{design.design_id}_{i}"
            triples += f"""
            {div_uri} rdf:type :Divider ;
                      :atPosition {x_pos} .
            {design_uri} :hasComponent {div_uri} .
            """

        # Link to reusable KB components if provided
        for comp_id in design.components_used:
            triples += f"""
            {design_uri} :usesComponent :component_{comp_id} .
            """
        
        return triples

    def _component_to_triples(self, component: KBComponent) -> str:
        """Convert KBComponent to RDF triples."""
        comp_uri = f":component_{component.component_id}"
        triples = f"""
        {comp_uri} rdf:type :Component ;
                    :componentID "{component.component_id}" ;
                    :componentType "{component.component_type}" ;
                    :componentWidth {component.width} ;
                    :componentHeight {component.height} ;
                    :componentDepth {component.depth} ;
                    :componentThickness {component.thickness} ;
                    :componentMaterial "{component.material}" ;
                    :stockQuantity {component.stock_quantity} ;
                    :componentStatus "{component.status}" .
        """
        if component.joint_pattern:
            triples += f"""
            {comp_uri} :jointPattern "{component.joint_pattern}" .
            """
        if component.last_used:
            triples += f"""
            {comp_uri} :lastUsed "{component.last_used}"^^xsd:dateTime .
            """
        return triples


def initialize_kb_with_samples():
    """Initialize KB with sample designs for testing"""
    kb = FusekiKBManager()
    
    if not kb.test_connection():
        logger.warning("Fuseki not available - KB features will be disabled")
        return None
    
    kb.create_dataset()
    
    # Add some standard designs
    samples = [
        KBDesign(
            design_id="STD-SMALL-001",
            width=600, height=1200, depth=300, thickness=18,
            add_top=True, material="melamine_pb",
            shelf_positions=[300, 600, 900],
            divider_positions=[],
            total_cost=125.50, max_load=150,
            generated_by="MANUAL",
            created_date=datetime.now().isoformat(),
            popularity_score=5
        ),
        KBDesign(
            design_id="STD-MEDIUM-001",
            width=800, height=1800, depth=350, thickness=18,
            add_top=True, material="melamine_pb",
            shelf_positions=[400, 800, 1200, 1600],
            divider_positions=[400],
            total_cost=185.75, max_load=200,
            generated_by="MANUAL",
            created_date=datetime.now().isoformat(),
            popularity_score=12
        ),
        KBDesign(
            design_id="STD-LARGE-001",
            width=1200, height=2000, depth=400, thickness=22,
            add_top=True, material="plywood",
            shelf_positions=[400, 800, 1200, 1600],
            divider_positions=[400, 800],
            total_cost=325.00, max_load=300,
            generated_by="MANUAL",
            created_date=datetime.now().isoformat(),
            popularity_score=8
        )
    ]
    
    for design in samples:
        kb.store_design(design)
    
    # Seed component inventory (panels, shelves, dividers)
    component_samples = [
        KBComponent(
            component_id="COMP-SIDE-1200-18",
            component_type="side_panel",
            width=18, height=1200, depth=300, thickness=18,
            material="melamine_pb",
            joint_pattern="camlock_grid",
            stock_quantity=6
        ),
        KBComponent(
            component_id="COMP-SIDE-1800-18",
            component_type="side_panel",
            width=18, height=1800, depth=350, thickness=18,
            material="melamine_pb",
            joint_pattern="camlock_grid",
            stock_quantity=4
        ),
        KBComponent(
            component_id="COMP-SHELF-800-18",
            component_type="shelf_board",
            width=764, height=18, depth=300, thickness=18,
            material="melamine_pb",
            joint_pattern="shelf_pin_grid",
            stock_quantity=12
        ),
        KBComponent(
            component_id="COMP-SHELF-1200-22",
            component_type="shelf_board",
            width=1156, height=22, depth=350, thickness=22,
            material="plywood",
            joint_pattern="shelf_pin_grid",
            stock_quantity=8
        ),
        KBComponent(
            component_id="COMP-DIV-400-18",
            component_type="divider",
            width=18, height=1800, depth=350, thickness=18,
            material="melamine_pb",
            joint_pattern="camlock_grid",
            stock_quantity=10
        ),
    ]

    for component in component_samples:
        kb.store_component(component)
    
    logger.info(f"Initialized KB with {len(samples)} sample designs and {len(component_samples)} stocked components")
    return kb
