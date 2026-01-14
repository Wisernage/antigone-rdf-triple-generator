#!/usr/bin/env python3
"""
Triple Validator for Antigone RDF Triples

Validates generated triple files against the ontology constraints:
- Property domain/range constraints
- Valid RDF/Turtle syntax
- Proper typing
- Correct prefix usage
"""

import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
from rdflib import Graph, URIRef, Namespace
from rdflib.namespace import RDF, RDFS, OWL, XSD
from collections import defaultdict

# Namespace
ANTIGONE = Namespace("http://example.org/antigone#")


class TripleValidator:
    """Validates RDF triples against ontology constraints."""
    
    def __init__(self, ontology_path: str = "Context/Ontology.ttl"):
        """
        Initialize validator with ontology.
        
        Args:
            ontology_path: Path to the ontology file
        """
        self.ontology_path = Path(ontology_path)
        self.ontology = Graph()
        self.errors = []
        self.warnings = []
        
        # Load ontology
        if not self.ontology_path.exists():
            raise FileNotFoundError(f"Ontology file not found: {self.ontology_path}")
        
        self.ontology.parse(str(self.ontology_path), format="turtle")
        self._extract_constraints()
    
    def _extract_constraints(self):
        """Extract property domain/range constraints from ontology."""
        self.property_domains = {}
        self.property_ranges = {}
        
        # Extract all object properties and their domains/ranges
        for prop in self.ontology.subjects(RDF.type, OWL.ObjectProperty):
            prop_uri = URIRef(prop)
            
            # Get domain
            domains = list(self.ontology.objects(prop_uri, RDFS.domain))
            if domains:
                # Handle union classes
                domain_list = []
                for domain in domains:
                    union_members = list(self.ontology.objects(domain, OWL.unionOf))
                    if union_members:
                        # It's a union - extract members
                        for member in self.ontology.items(union_members[0]):
                            domain_list.append(member)
                    else:
                        domain_list.append(domain)
                self.property_domains[prop_uri] = domain_list
            
            # Get range
            ranges = list(self.ontology.objects(prop_uri, RDFS.range))
            if ranges:
                range_list = []
                for range_val in ranges:
                    union_members = list(self.ontology.objects(range_val, OWL.unionOf))
                    if union_members:
                        # It's a union - extract members
                        for member in self.ontology.items(union_members[0]):
                            range_list.append(member)
                    else:
                        range_list.append(range_val)
                self.property_ranges[prop_uri] = range_list
    
    def _get_individual_types(self, graph: Graph, individual: URIRef) -> Set[URIRef]:
        """Get all types of an individual."""
        types = set()
        for obj in graph.objects(individual, RDF.type):
            types.add(obj)
        return types
    
    def _check_property_constraint(self, graph: Graph, subject: URIRef, predicate: URIRef, object_val: URIRef):
        """Check if a triple violates domain/range constraints."""
        predicate_uri = URIRef(predicate)
        
        # Check domain
        if predicate_uri in self.property_domains:
            subject_types = self._get_individual_types(graph, subject)
            allowed_domains = self.property_domains[predicate_uri]
            
            # Check if subject type matches any allowed domain
            domain_match = False
            for domain in allowed_domains:
                if domain in subject_types or domain == OWL.Thing:
                    domain_match = True
                    break
            
            if not domain_match and subject_types:
                self.errors.append(
                    f"Domain violation: {predicate.n3(graph.namespace_manager)} "
                    f"requires domain {[str(d) for d in allowed_domains]}, "
                    f"but subject {subject.n3(graph.namespace_manager)} has types {[str(t) for t in subject_types]}"
                )
        
        # Check range
        if predicate_uri in self.property_ranges:
            object_types = self._get_individual_types(graph, object_val)
            allowed_ranges = self.property_ranges[predicate_uri]
            
            # Check if object type matches any allowed range
            range_match = False
            for range_val in allowed_ranges:
                if range_val in object_types or range_val == OWL.Thing:
                    range_match = True
                    break
            
            if not range_match and object_types:
                self.errors.append(
                    f"Range violation: {predicate.n3(graph.namespace_manager)} "
                    f"requires range {[str(r) for r in allowed_ranges]}, "
                    f"but object {object_val.n3(graph.namespace_manager)} has types {[str(t) for t in object_types]}"
                )
    
    def _extract_entity_names_from_text(self, text: str) -> Set[str]:
        """Extract potential entity names from description text."""
        import re
        # Common character and concept names in Antigone
        known_entities = {
            'antigone', 'creon', 'ismene', 'haemon', 'teiresias', 'chorus',
            'polyneices', 'eteocles', 'oedipus', 'jocasta',
            'eros', 'desire', 'justice', 'law', 'fate', 'gods', 'divine',
            'miasma', 'bloodguilt', 'polis', 'city'
        }
        
        text_lower = text.lower()
        found_entities = set()
        
        # Check for known entities
        for entity in known_entities:
            if entity in text_lower:
                found_entities.add(entity)
        
        # Extract capitalized words that might be entities
        capitalized_words = re.findall(r'\b[A-Z][a-z]+\b', text)
        for word in capitalized_words:
            if word.lower() in known_entities:
                found_entities.add(word.lower())
        
        return found_entities
    
    def _get_individual_local_name(self, uri: URIRef) -> str:
        """Extract local name from URI."""
        uri_str = str(uri)
        if '#' in uri_str:
            return uri_str.split('#')[-1]
        elif '/' in uri_str:
            return uri_str.split('/')[-1]
        return uri_str
    
    def _check_semantic_issues(self, graph: Graph):
        """Check for semantic/logical issues in the triples."""
        # Get all individuals and their types
        individuals = {}
        for subject, predicate, object_val in graph:
            if predicate == RDF.type:
                if subject not in individuals:
                    individuals[subject] = set()
                individuals[subject].add(object_val)
        
        # Build a map of entity names to URIs for conflict checking
        entity_name_map = {}
        for individual, types in individuals.items():
            local_name = self._get_individual_local_name(individual)
            # Extract base name (e.g., "Antigone_Character_Antigone" -> "Antigone")
            parts = local_name.split('_')
            if len(parts) >= 3:
                base_name = parts[-1].lower()
                if base_name not in entity_name_map:
                    entity_name_map[base_name] = []
                entity_name_map[base_name].append(individual)
        
        # Check for naming inconsistencies in Characters
        character_names = {}
        for individual, types in individuals.items():
            if ANTIGONE.Character in types:
                local_name = self._get_individual_local_name(individual)
                parts = local_name.split('_')
                if len(parts) >= 3 and parts[1] == 'Character':
                    character_name = parts[0]
                    identifier_name = parts[-1] if len(parts) > 2 else None
                    
                    # Check for contradictions like "Antigone_Character_Chorus"
                    if identifier_name and character_name != identifier_name:
                        # Check if this looks like a mistake (e.g., Antigone_Character_Chorus)
                        common_names = ['chorus', 'creon', 'ismene', 'haemon', 'teiresias', 'antigone', 'polyneices', 'eteocles']
                        if identifier_name.lower() in common_names and \
                           character_name.lower() != identifier_name.lower():
                            self.warnings.append(
                                f"Potential naming inconsistency: {individual.n3(graph.namespace_manager)} "
                                f"has character name '{character_name}' but identifier suggests '{identifier_name}'"
                            )
                    
                    # Track character names for consistency checking
                    if character_name not in character_names:
                        character_names[character_name] = []
                    character_names[character_name].append(individual)
        
        # Check for inconsistent naming patterns across all entity types
        naming_patterns = defaultdict(list)
        for individual, types in individuals.items():
            local_name = self._get_individual_local_name(individual)
            parts = local_name.split('_')
            if len(parts) >= 2:
                # Pattern: Type_Subtype_Name or Type_Name
                pattern_key = '_'.join(parts[:-1]) if len(parts) > 2 else parts[0]
                naming_patterns[pattern_key].append((individual, parts[-1]))
        
        # Check for inconsistent naming within same pattern
        for pattern, entities in naming_patterns.items():
            if len(entities) > 1:
                names = [name for _, name in entities]
                # Check if names follow consistent capitalization
                capitalized = sum(1 for name in names if name and name[0].isupper())
                if capitalized > 0 and capitalized < len(names):
                    self.warnings.append(
                        f"Inconsistent capitalization in naming pattern '{pattern}': "
                        f"some entities use capitalized names, others don't"
                    )
        
        # Check conflicts for semantic issues
        conflicts = {}
        conflict_descriptions = {}
        for subject, predicate, object_val in graph:
            if predicate == ANTIGONE.conflictBetween:
                conflict_uri = subject
                participant = object_val
                if conflict_uri not in conflicts:
                    conflicts[conflict_uri] = []
                conflicts[conflict_uri].append(participant)
            elif predicate == ANTIGONE.description:
                conflict_descriptions[subject] = str(object_val)
        
        # Check for conflicts with insufficient participants and missing entities in descriptions
        for conflict_uri, participants in conflicts.items():
            if len(participants) < 2:
                self.warnings.append(
                    f"Conflict {conflict_uri.n3(graph.namespace_manager)} has only {len(participants)} participant(s). "
                    f"Conflicts typically involve at least two opposing entities."
                )
            
            # Check if description mentions entities not listed as participants
            if conflict_uri in conflict_descriptions:
                description = conflict_descriptions[conflict_uri]
                mentioned_entities = self._extract_entity_names_from_text(description)
                
                # Get participant names
                participant_names = set()
                for participant in participants:
                    local_name = self._get_individual_local_name(participant)
                    parts = local_name.split('_')
                    if len(parts) >= 3:
                        participant_names.add(parts[-1].lower())
                    elif len(parts) >= 2:
                        participant_names.add(parts[-1].lower())
                
                # Check for mentioned entities that aren't participants
                missing_entities = []
                for entity in mentioned_entities:
                    # Check if entity matches any participant name
                    found = False
                    for part_name in participant_names:
                        if entity in part_name or part_name in entity:
                            found = True
                            break
                    if not found:
                        missing_entities.append(entity)
                
                if missing_entities and len(participants) < 2:
                    self.warnings.append(
                        f"Conflict {conflict_uri.n3(graph.namespace_manager)} description mentions "
                        f"'{', '.join(missing_entities)}' but these entities are not listed as participants. "
                        f"Consider adding them if they represent opposing forces."
                    )
        
        # Check for missing relationships - Characters should typically have motivations, decisions, or emotions
        for individual, types in individuals.items():
            if ANTIGONE.Character in types:
                has_motivation = any(graph.objects(individual, ANTIGONE.hasMotivation))
                has_decision = any(graph.objects(individual, ANTIGONE.makesMoralDecision))
                has_emotion = any(graph.objects(individual, ANTIGONE.experiencesEmotion))
                has_advocacy = any(graph.objects(individual, ANTIGONE.advocatesFor))
                
                # Characters that appear but have no relationships might be incomplete
                if not (has_motivation or has_decision or has_emotion or has_advocacy):
                    # Check if character appears in any other relationships
                    has_any_relationship = False
                    for pred, obj in graph.predicate_objects(individual):
                        if pred not in [RDF.type, ANTIGONE.description]:
                            has_any_relationship = True
                            break
                    
                    if not has_any_relationship:
                        self.warnings.append(
                            f"Character {individual.n3(graph.namespace_manager)} has no motivations, decisions, "
                            f"emotions, or advocacy relationships. Consider adding relevant relationships."
                        )
        
        # Check for duplicate characters with different names
        character_by_role = {}
        for individual, types in individuals.items():
            if ANTIGONE.Character in types:
                # Try to get role description
                role_descriptions = list(graph.objects(individual, ANTIGONE.role))
                if role_descriptions:
                    role = str(role_descriptions[0])
                    if role not in character_by_role:
                        character_by_role[role] = []
                    character_by_role[role].append(individual)
        
        for role, chars in character_by_role.items():
            if len(chars) > 1:
                # Multiple characters with same role - might be intentional (e.g., multiple guards)
                # but worth checking if they have different names
                char_names = [str(c).split('_')[0] for c in chars]
                if len(set(char_names)) > 1:
                    self.warnings.append(
                        f"Multiple characters with role '{role}' but different names: {[c.n3(graph.namespace_manager) for c in chars]}"
                    )
    
    def validate_file(self, triple_file: Path) -> Tuple[bool, List[str], List[str]]:
        """
        Validate a triple file.
        
        Args:
            triple_file: Path to the triple file to validate
            
        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []
        
        if not triple_file.exists():
            self.errors.append(f"File not found: {triple_file}")
            return False, self.errors, self.warnings
        
        # Parse the triple file
        graph = Graph()
        try:
            graph.parse(str(triple_file), format="turtle")
        except Exception as e:
            self.errors.append(f"Syntax error: {str(e)}")
            return False, self.errors, self.warnings
        
        # Check all triples
        for subject, predicate, object_val in graph:
            # Skip RDF type triples for now (we check types separately)
            if predicate == RDF.type:
                continue
            
            # Check property constraints
            if isinstance(object_val, URIRef):
                self._check_property_constraint(graph, subject, predicate, object_val)
        
        # Check that all individuals are properly typed
        individuals = set()
        for subject, predicate, object_val in graph:
            if predicate == RDF.type:
                individuals.add(subject)
        
        for individual in individuals:
            types = self._get_individual_types(graph, individual)
            if not types:
                self.warnings.append(
                    f"Individual {individual.n3(graph.namespace_manager)} has no explicit type"
                )
            elif ANTIGONE.Character not in types and ANTIGONE.Motivation not in types and \
                 ANTIGONE.Emotion not in types and ANTIGONE.Theme not in types and \
                 ANTIGONE.Conflict not in types and ANTIGONE.MoralDecision not in types and \
                 ANTIGONE.EthicalPrinciple not in types:
                # Check if it's at least typed as something
                if OWL.NamedIndividual not in types and OWL.Thing not in types:
                    self.warnings.append(
                        f"Individual {individual.n3(graph.namespace_manager)} may need explicit ontology type"
                    )
        
        # Check for semantic issues
        self._check_semantic_issues(graph)
        
        return len(self.errors) == 0, self.errors, self.warnings
    
    def validate_directory(self, productions_dir: str = "[PRODUCTIONS]") -> Dict[str, Tuple[bool, List[str], List[str]]]:
        """
        Validate all triple files in a directory.
        
        Args:
            productions_dir: Path to the [PRODUCTIONS] directory
            
        Returns:
            Dictionary mapping file paths to (is_valid, errors, warnings)
        """
        results = {}
        productions_path = Path(productions_dir)
        
        if not productions_path.exists():
            print(f"Error: Directory not found: {productions_path}")
            return results
        
        # Find all verse range directories
        for verse_dir in productions_path.iterdir():
            if verse_dir.is_dir() and verse_dir.name.startswith('verse_'):
                # Find triple files
                for triple_file in verse_dir.glob('triples_*.ttl'):
                    is_valid, errors, warnings = self.validate_file(triple_file)
                    results[str(triple_file)] = (is_valid, errors, warnings)
        
        return results


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Validate RDF/Turtle triple files against the Antigone ontology'
    )
    parser.add_argument(
        '--ontology',
        type=str,
        default='Context/Ontology.ttl',
        help='Path to the ontology file (default: Context/Ontology.ttl)'
    )
    parser.add_argument(
        '--file',
        type=str,
        default=None,
        help='Validate a specific file'
    )
    parser.add_argument(
        '--productions-dir',
        type=str,
        default='[PRODUCTIONS]',
        help='Path to the [PRODUCTIONS] directory (default: [PRODUCTIONS])'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show warnings in addition to errors'
    )
    
    args = parser.parse_args()
    
    try:
        validator = TripleValidator(args.ontology)
        
        if args.file:
            # Validate single file
            triple_file = Path(args.file)
            is_valid, errors, warnings = validator.validate_file(triple_file)
            
            print(f"\nValidating: {triple_file}")
            print("=" * 70)
            
            if is_valid:
                if warnings:
                    print("[OK] VALID - No constraint violations")
                    print("\nSemantic warnings:")
                    for warning in warnings:
                        print(f"  WARNING: {warning}")
                else:
                    print("[OK] VALID - No errors or warnings found")
            else:
                print("[ERROR] INVALID - Constraint violations found:")
                for error in errors:
                    print(f"  ERROR: {error}")
            
            if warnings and not is_valid:
                print("\nSemantic warnings:")
                for warning in warnings:
                    print(f"  WARNING: {warning}")
            
            sys.exit(0 if is_valid else 1)
        else:
            # Validate all files in directory
            results = validator.validate_directory(args.productions_dir)
            
            if not results:
                print("No triple files found to validate.")
                sys.exit(0)
            
            print(f"\nValidating {len(results)} triple file(s)...")
            print("=" * 70)
            
            all_valid = True
            total_warnings = 0
            for file_path, (is_valid, errors, warnings) in results.items():
                file_name = Path(file_path).name
                if is_valid:
                    if warnings:
                        print(f"[OK] {file_name}: VALID (but has {len(warnings)} warning(s))")
                        for warning in warnings:
                            print(f"    WARNING: {warning}")
                        total_warnings += len(warnings)
                    else:
                        print(f"[OK] {file_name}: VALID")
                else:
                    print(f"[ERROR] {file_name}: INVALID")
                    for error in errors:
                        print(f"    ERROR: {error}")
                    all_valid = False
                    if warnings:
                        for warning in warnings:
                            print(f"    WARNING: {warning}")
                    total_warnings += len(warnings)
            
            print("\n" + "=" * 70)
            if all_valid:
                if total_warnings > 0:
                    print(f"[OK] All files are syntactically valid, but {total_warnings} semantic warning(s) found.")
                else:
                    print("[OK] All files are valid!")
            else:
                print("[ERROR] Some files have constraint violations. Please fix them.")
                if total_warnings > 0:
                    print(f"Also found {total_warnings} semantic warning(s).")
            
            sys.exit(0 if all_valid else 1)
    
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
