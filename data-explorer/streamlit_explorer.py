#!/usr/bin/env python3
"""
Graphiti Knowledge Graph Explorer
A Streamlit app for exploring and visualizing Graphiti knowledge graphs
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
from neo4j import GraphDatabase
import json
from datetime import datetime, timedelta
import os
from typing import Dict, List, Any, Tuple
from streamlit_agraph import agraph, Node, Edge, Config
import base64
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def safe_property_value(value: Any) -> str:
    """Safely convert any property value to a displayable string"""
    if value is None:
        return "None"
    elif isinstance(value, (str, int, float, bool)):
        return str(value)
    elif isinstance(value, list):
        if len(value) == 0:
            return "[]"
        elif len(value) <= 3:
            return f"[{', '.join(str(v) for v in value)}]"
        else:
            return f"[{', '.join(str(v) for v in value[:3])}, ... (+{len(value)-3} more)]"
    elif isinstance(value, dict):
        return f"{{...}} ({len(value)} keys)"
    else:
        return str(value)[:100] + ("..." if len(str(value)) > 100 else "")

# Configure Streamlit page
st.set_page_config(
    page_title="Graphiti Explorer",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .entity-card {
        background-color: #ffffff;
        padding: 1rem;
        border-radius: 0.5rem;
        border: 1px solid #e1e5e9;
        margin-bottom: 0.5rem;
    }
    .relationship-badge {
        background-color: #e1f5fe;
        padding: 0.25rem 0.5rem;
        border-radius: 1rem;
        font-size: 0.8rem;
        margin: 0.2rem;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

class GraphitiExplorer:
    def __init__(self):
        self.driver = None
        self.connected = False
        
    def connect_to_neo4j(self, uri: str, username: str, password: str) -> bool:
        """Connect to Neo4j database"""
        self.driver = create_connection(uri, username, password)
        self.connected = self.driver is not None
        return self.connected
    
    def close_connection(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
    
    def run_query(self, query: str, parameters: dict = None) -> List[Dict]:
        """Execute a Neo4j query and return results"""
        if not self.connected:
            return []
        
        try:
            with self.driver.session() as session:
                data, error = safe_query(session, query, parameters, "Query")
                if error:
                    st.error(error)
                return data
        except Exception as e:
            st.error(f"Query execution failed: {str(e)}")
            return []
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get overall database statistics"""
        stats_data = get_database_stats(self.driver) 
        
        if stats_data.get('error'): 
            st.error(f"Failed to retrieve database statistics: {stats_data['error']}")
            return {"labels": [], "relationship_types": [], "total_nodes": 0, "total_relationships": 0, "error": stats_data['error']}
        
        return stats_data
        
    def get_entity_details(self, entity_id: str) -> List[Dict]:
        """Get detailed information about an entity"""
        query = """
        MATCH (n {uuid: $entity_id})
        RETURN n
        """
        return self.run_query(query, {'entity_id': entity_id})

    def get_recent_episodes(self, limit: int = 10) -> List[Dict]:
        """Get recent episodic nodes from the graph, ordered by creation time."""
        query = """
        MATCH (e:Episodic)
        RETURN e
        ORDER BY e.created_at DESC
        LIMIT $limit
        """
        return self.run_query(query, {'limit': limit})

    def get_entity_relationships_for_table(self, entity_uuid: str) -> List[Dict]:
        """Fetch all relationships for a given entity, formatted for a table."""
        query = """
        MATCH (source {uuid: $entity_uuid})-[r]-(target)
        RETURN
            source.name AS source_name,
            type(r) AS relationship_type,
            properties(r) as relationship_properties,
            target.name AS target_name,
            labels(target) as target_labels
        """
        results = self.run_query(query, {'entity_uuid': entity_uuid})
        
        table_data = []
        for record in results:
            rel_props = record.get('relationship_properties', {})
            table_data.append({
                "Source": record.get('source_name'),
                "Relationship": record.get('relationship_type'),
                "Target": record.get('target_name'),
                "Target Labels": record.get('target_labels', []),
                "Relationship Properties": json.dumps({k: safe_property_value(v) for k, v in rel_props.items()}, indent=2) if rel_props else "{}"
            })
        return table_data

    def get_communities(self, limit: int = 20) -> List[Dict]:
        """Get community nodes from the graph"""
        query = """
        MATCH (c:Community)
        RETURN c
        ORDER BY c.name ASC
        LIMIT $limit
        """
        return self.run_query(query, {'limit': limit})

def create_connection(uri, user, password):
    """Create Neo4j connection with proper error handling"""
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        # Test the connection
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            result.single()
        st.success("✅ Successfully connected to Neo4j!")
        logger.info(f"Connected to Neo4j at {uri}")
        return driver
    except Exception as e:
        st.error(f"❌ Failed to connect to Neo4j: {str(e)}")
        logger.error(f"Neo4j connection failed: {str(e)}")
        return None

def safe_query(session, query, parameters=None, description="Query"):
    """Execute query with comprehensive error handling"""
    try:
        logger.info(f"Executing {description}: {query}")
        if parameters:
            logger.info(f"Parameters: {parameters}")
        
        result = session.run(query, parameters or {})
        data = [record.data() for record in result]
        logger.info(f"{description} returned {len(data)} records")
        return data, None
    except Exception as e:
        error_msg = f"{description} failed: {str(e)}"
        logger.error(error_msg)
        return [], error_msg

def get_database_stats(driver):
    """Get database statistics with error handling"""
    if not driver:
        return {"error": "No database driver available.", "labels": [], "relationship_types": [], "total_nodes": 0, "total_relationships": 0}
        
    try:
        with driver.session() as session:
            labels_data, labels_error = safe_query(session, "CALL db.labels()", description="Labels query")
            if labels_error:
                logger.warning(f"Could not fetch labels: {labels_error}")
                return {"error": f"Labels query failed: {labels_error}", "labels": [], "relationship_types": [], "total_nodes": 0, "total_relationships": 0}

            labels = [record['label'] for record in labels_data] if labels_data else []
            
            rel_types_data, rel_error = safe_query(session, "CALL db.relationshipTypes()", description="Relationship types query")
            if rel_error:
                logger.warning(f"Could not fetch relationship types: {rel_error}")
                return {"error": f"Relationship types query failed: {rel_error}", "labels": labels, "relationship_types": [], "total_nodes": 0, "total_relationships": 0}

            rel_types = [record['relationshipType'] for record in rel_types_data] if rel_types_data else []
            
            node_count_data, node_error = safe_query(session, "MATCH (n) RETURN count(n) as count", description="Node count query")
            total_nodes = node_count_data[0]['count'] if node_count_data and not node_error else 0
            if node_error: logger.warning(f"Node count query failed: {node_error}")

            rel_count_data, rel_count_error = safe_query(session, "MATCH ()-[r]->() RETURN count(r) as count", description="Relationship count query")
            total_relationships = rel_count_data[0]['count'] if rel_count_data and not rel_count_error else 0
            if rel_count_error: logger.warning(f"Relationship count query failed: {rel_count_error}")
            
            errors_list = [e for e in [labels_error, rel_error, node_error, rel_count_error] if e]

            return {
                "labels": labels,
                "relationship_types": rel_types,
                "total_nodes": total_nodes,
                "total_relationships": total_relationships,
                "error": "; ".join(errors_list) if errors_list else None
            }
            
    except Exception as e:
        error_msg = f"Database stats query failed: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "labels": [], "relationship_types": [], "total_nodes": 0, "total_relationships": 0}

def render_entity_exploration_page(explorer: GraphitiExplorer):
    st.header("🏷️ Explore Entities")
    st.write("Deep dive into semantic entities, their properties, and connections. Search for an entity to see its details and local graph neighborhood.")

    search_term_entities = st.text_input("Search for an Entity (by name, UUID, or summary keyword):", key="entity_search_term_input")
    
    selected_entity_uuid = st.session_state.get('selected_entity_uuid_for_exploration', None)

    if search_term_entities:
        with st.spinner(f"Searching for entities matching '{search_term_entities}'..."):
            query = """
            MATCH (n:Entity)
            WHERE n.name CONTAINS $search_term 
               OR n.uuid = $search_term 
               OR (n.summary IS NOT NULL AND n.summary CONTAINS $search_term)
            RETURN n.uuid as uuid, n.name as name, labels(n) as labels, n.summary as summary
            LIMIT 10
            """
            results = explorer.run_query(query, {'search_term': search_term_entities})

        if results:
            st.subheader("Search Results:")
            entity_options = {f"{res.get('name', 'Unnamed Entity')} ({res['uuid']})": res['uuid'] for res in results if res.get('uuid')}
            
            if not entity_options:
                st.write("No entities found with a displayable name and UUID.")
            else:
                # Use a button for each search result to trigger selection
                for display_name, uuid_val in entity_options.items():
                    if st.button(display_name, key=f"select_entity_{uuid_val}"):
                        st.session_state.selected_entity_uuid_for_exploration = uuid_val
                        selected_entity_uuid = uuid_val # Update for current run
                        st.rerun() # Rerun to process selection
        else:
            st.write("No entities found matching your search term.")
    
    if selected_entity_uuid:
        st.markdown("---")
        # Fetch fresh details in case button state is tricky
        entity_details_data = explorer.get_entity_details(selected_entity_uuid)
        
        if entity_details_data and entity_details_data[0].get('n'):
            selected_entity_details = entity_details_data[0]['n']
            st.subheader(f"Exploring Entity: {selected_entity_details.get('name', selected_entity_uuid)}")
            
            st.markdown("**Entity Properties:**")
            props_to_display = {k: safe_property_value(v) for k, v in selected_entity_details.items() if k not in ['name_embedding']}
            num_props = len(props_to_display)
            cols_per_row = 3
            prop_items = list(props_to_display.items())
            
            for i in range(0, num_props, cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < num_props:
                        key, value = prop_items[i+j]
                        with cols[j]:
                            st.markdown(f"**{key.replace('_', ' ').title()}:**")
                            # Use st.caption or st.code for value to handle long strings better
                            if len(value) > 70:
                                st.caption(value)
                            else:
                                st.markdown(f"`{value}`")
            
            if 'summary' in selected_entity_details and selected_entity_details['summary']:
                 with st.expander("Full Summary", expanded=False):
                        st.markdown(selected_entity_details['summary'])
            
            st.markdown("**Entity Relationships Table:**")
            with st.spinner("Loading entity relationships..."):
                relationships = explorer.get_entity_relationships_for_table(selected_entity_uuid)

            if relationships:
                df = pd.DataFrame(relationships)
                # Reorder columns for better readability
                display_cols = ["Source", "Relationship", "Target", "Target Labels", "Relationship Properties"]
                # Ensure all columns exist before trying to display them
                existing_cols = [col for col in display_cols if col in df.columns]
                st.dataframe(df[existing_cols], use_container_width=True)
            else:
                st.info("This entity has no direct relationships.")
        else:
            st.error(f"Could not retrieve details for entity UUID: {selected_entity_uuid}")
            st.session_state.selected_entity_uuid_for_exploration = None # Clear selection on error

def render_episodic_data_page(explorer: GraphitiExplorer):
    st.header("📝 Explore Episodic Data")
    st.write("Browse through raw episodic data, such as conversation chunks or ingested documents. The most recent episodes are listed first.")

    limit = st.slider("Number of recent episodes to display:", 5, 50, 10)

    with st.spinner("Loading recent episodes..."):
        episodes = explorer.get_recent_episodes(limit=limit)

    if not episodes:
        st.info("No episodic data found in the graph.")
        return

    st.subheader(f"Displaying {len(episodes)} Most Recent Episodes")
    for episode_data in episodes:
        episode = episode_data.get('e') # The query returns records with key 'e'
        if not episode:
            st.warning("Found an episode entry with missing data.")
            continue

        episode_name = episode.get('name', episode.get('uuid', 'Unnamed Episode'))
        episode_source = episode.get('source', 'Unknown source')
        episode_created_at = episode.get('created_at', 'N/A')
        if isinstance(episode_created_at, (int, float)):
             try:
                episode_created_at = datetime.fromtimestamp(episode_created_at).strftime('%Y-%m-%d %H:%M:%S')
             except:
                episode_created_at = str(episode_created_at) # fallback if timestamp is unusual
        
        # Display summary in an expander
        with st.expander(f"**{episode_name}** (Source: {episode_source} | Created: {episode_created_at})"):
            st.markdown("**Full Episode Details:**")
            
            # Display all properties except potentially very long ones like embeddings or full content here
            props_to_display = {k: safe_property_value(v) for k, v in episode.items() 
                                if k not in ['content', 'name_embedding', 'entity_edges_embedding']}
            num_props = len(props_to_display)
            cols_per_row = 2
            prop_items = list(props_to_display.items())
            
            for i in range(0, num_props, cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < num_props:
                        key, value = prop_items[i+j]
                        with cols[j]:
                            st.markdown(f"**{key.replace('_', ' ').title()}:**")
                            if len(value) > 100:
                                st.caption(value)
                            else:
                                st.markdown(f"`{value}`")
            
            if 'content' in episode and episode['content']:
                st.markdown("**Content:**")
                st.markdown(f"```text\n{episode['content']}\n```")
            
            if 'entity_edges' in episode and episode['entity_edges']:
                st.markdown("**Mentioned Entity Edges (UUIDs):**")
                if isinstance(episode['entity_edges'], list) and episode['entity_edges']:
                    for edge_uuid in episode['entity_edges']:
                        st.markdown(f"- `{edge_uuid}`")
                    # TODO: Optionally, make these clickable to navigate to entity explorer or fetch edge details
                elif episode['entity_edges']:
                    st.caption(safe_property_value(episode['entity_edges']))
                else:
                    st.caption("No entity edges listed.")

def render_communities_page(explorer: GraphitiExplorer):
    st.header("👥 Explore Communities")
    st.write("Discover communities or clusters of related entities within your graph.")

    with st.spinner("Loading communities..."):
        communities_data = explorer.get_communities(limit=50)

    if not communities_data:
        st.info("No 'Community' nodes found in your knowledge graph at this time. "
                "Communities can be created by Graphiti to represent clusters of related entities.")
        st.markdown("""
            **What are Communities?**
            Communities in Graphiti typically represent:
            - Semantic groupings of entities based on shared characteristics or relationships.
            - Clusters identified through graph algorithms or explicit user definition.
            - Higher-level abstractions that can provide insights into the overall structure of your knowledge.

            Once communities are present, this page will allow you to explore their members, summaries, and connections.
        """)
        return

    st.subheader(f"Found {len(communities_data)} Communities")
    for community_item in communities_data:
        community = community_item.get('c') # Assuming query returns 'c'
        if not community:
            st.warning("Found a community entry with missing data.")
            continue

        community_name = community.get('name', community.get('uuid', 'Unnamed Community'))
        
        with st.expander(f"**Community: {community_name}**"):
            st.markdown("**Community Properties:**")
            props_to_display = {k: safe_property_value(v) for k, v in community.items() if k != 'name_embedding'}
            # Simple list display for now
            for key, value in props_to_display.items():
                st.markdown(f"- **{key.replace('_', ' ').title()}:** `{value}`")
            
            # Placeholder for community members or further details
            st.markdown("**Further Exploration (Placeholder):**")
            st.caption("Details about community members and visualization will be implemented here.")

def main():
    st.markdown('<h1 class="main-header">🧠 Graphiti Knowledge Graph Explorer</h1>', unsafe_allow_html=True)
    
    if 'explorer' not in st.session_state:
        st.session_state.explorer = GraphitiExplorer()
    
    explorer = st.session_state.explorer
    
    st.sidebar.header("🔌 Database Connection")
    default_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    default_user = os.getenv('NEO4J_USER', 'neo4j')
    default_password = os.getenv('NEO4J_PASSWORD', 'demodemo')
    
    neo4j_uri = st.sidebar.text_input("Neo4j URI", value=default_uri)
    neo4j_user = st.sidebar.text_input("Username", value=default_user)
    neo4j_password = st.sidebar.text_input("Password", value=default_password, type="password")
    
    if st.sidebar.button("Connect"):
        if explorer.connect_to_neo4j(neo4j_uri, neo4j_user, neo4j_password):
            st.sidebar.success("✅ Connected to Neo4j!")
            st.rerun() # Force rerun to update page content after connection
        else:
            st.sidebar.error("❌ Connection failed!")
            
    if not explorer.connected:
        st.warning("👋 Welcome! Please connect to your Neo4j database using the sidebar to start exploring your Graphiti knowledge graph.")
        st.markdown("""
        Graphiti allows you to explore:
        - **🏷️ Entities**: Rich, interconnected semantic objects.
        - **📝 Episodic Data**: Raw textual or structured data episodes.
        - **👥 Communities**: Clusters of related entities.
        
        Connect to see them in action!
        """)
        return

    # Sidebar Navigation
    st.sidebar.title("📄 Navigation")
    page_options = ["📊 Overview", "🏷️ Explore Entities", "📝 Explore Episodic Data", "👥 Explore Communities"]
    
    if 'current_page' not in st.session_state:
        st.session_state.current_page = page_options[0]

    selected_page_from_radio = st.sidebar.radio(
        "Go to", 
        page_options, 
        index=page_options.index(st.session_state.current_page),
        key="navigation_radio"
    )

    if selected_page_from_radio != st.session_state.current_page:
        st.session_state.current_page = selected_page_from_radio
        st.rerun() # Rerun on page change for clean state

    # Page rendering based on selection
    if st.session_state.current_page == "📊 Overview":
        show_overview(explorer) # Assuming show_overview is kept
    elif st.session_state.current_page == "🏷️ Explore Entities":
        render_entity_exploration_page(explorer)
    elif st.session_state.current_page == "📝 Explore Episodic Data":
        render_episodic_data_page(explorer)
    elif st.session_state.current_page == "👥 Explore Communities":
        render_communities_page(explorer)

def show_overview(explorer: GraphitiExplorer):
    """Display database overview and statistics"""
    st.header("📊 Database Overview")
    
    with st.spinner("Loading database statistics..."):
        stats = explorer.get_database_stats()
    
    if not stats:
        st.warning("No data found in the database.")
        return
    
    # Display key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Nodes", stats.get('total_nodes', 0))
    
    with col2:
        st.metric("Total Relationships", stats.get('total_relationships', 0))
    
    with col3:
        st.metric("Node Types", len(stats.get('labels', [])))
    
    with col4:
        st.metric("Relationship Types", len(stats.get('relationship_types', [])))
    
    # Node distribution chart
    if stats.get('labels'):
        st.subheader("📈 Node Distribution by Type")
        node_df = pd.DataFrame(stats['labels'], columns=['Type'])
        node_df['Count'] = 1
        fig_nodes = px.pie(node_df, values='Count', names='Type', title="Distribution of Node Types")
        st.plotly_chart(fig_nodes, use_container_width=True)
    
    # Relationship distribution chart
    if stats.get('relationship_types'):
        st.subheader("🔗 Relationship Distribution by Type")
        rel_df = pd.DataFrame(stats['relationship_types'], columns=['Type'])
        rel_df['Count'] = 1
        fig_rels = px.bar(rel_df, x='Type', y='Count', title="Count of Relationships by Type")
        st.plotly_chart(fig_rels, use_container_width=True)

if __name__ == "__main__":
    main()
