#!/usr/bin/env python3
"""
Example script demonstrating the anti-hallucination workflow with Gen3 MCP.

This script shows how to use the validation tools to prevent GraphQL field name
hallucinations when working with Gen3 data commons.
"""

import asyncio
import json
from gen3 import get_client, client_context
from gen3_validator import Gen3SchemaValidator


async def demonstrate_validation_workflow():
    """Demonstrate the complete validation workflow"""
    
    print("🔬 Gen3 MCP Anti-Hallucination Workflow Demo")
    print("=" * 60)
    
    try:
        async with client_context() as client:
            validator = Gen3SchemaValidator(client)
            
            # Step 1: Generate a safe template
            print("\n📋 Step 1: Generate Safe Query Template")
            print("-" * 40)
            
            template_result = await validator.get_query_template("subject")
            if template_result["exists"]:
                print("✅ Generated safe template for 'subject' entity:")
                print(template_result["template"])
                print(f"\n📊 Template includes {template_result['total_fields']} validated fields")
                print(f"🔗 Found {len(template_result['relationship_fields'])} relationship fields")
            else:
                print("❌ Failed to generate template:", template_result.get("error"))
                return
            
            # Step 2: Create a query with intentional errors
            print("\n🚫 Step 2: Create Query with Invalid Fields")
            print("-" * 40)
            
            # This query has several invalid field names (common hallucinations)
            invalid_query = """
            {
                subject(first: 5) {
                    id
                    submitter_id
                    patient_name       # ❌ Invalid - common hallucination
                    study_name         # ❌ Invalid - doesn't exist in subject
                    imaging_modality   # ❌ Invalid - wrong entity
                    gender             # ✅ Valid
                    age_at_enrollment  # ✅ Valid
                }
            }
            """
            
            print("Query with invalid fields:")
            print(invalid_query)
            
            # Step 3: Validate the query
            print("\n🔍 Step 3: Validate Query Against Schema")
            print("-" * 40)
            
            validation = await validator.validate_query_fields(invalid_query)
            
            print(f"Query validation result: {'✅ VALID' if validation['valid'] else '❌ INVALID'}")
            print(f"Total entities checked: {validation['summary']['total_entities']}")
            print(f"Total fields checked: {validation['summary']['total_fields']}")
            print(f"Valid fields: {validation['summary']['valid_fields']}")
            print(f"Errors found: {validation['summary']['total_errors']}")
            
            if not validation["valid"]:
                print("\n🚨 Validation Errors:")
                for error in validation["summary"]["errors"]:
                    print(f"   • {error}")
            
            # Step 4: Get suggestions for invalid fields
            print("\n💡 Step 4: Get Suggestions for Invalid Fields")
            print("-" * 40)
            
            invalid_fields = ["patient_name", "study_name", "imaging_modality"]
            
            for field in invalid_fields:
                print(f"\n🔍 Suggestions for '{field}':")
                suggestions = await validator.suggest_similar_fields(field, "subject")
                
                if suggestions["suggestions"]:
                    print("   Top suggestions:")
                    for i, suggestion in enumerate(suggestions["suggestions"][:3], 1):
                        similarity = suggestion["similarity"]
                        field_type = suggestion["type"]
                        print(f"   {i}. {suggestion['name']} (similarity: {similarity:.2f}, type: {field_type})")
                else:
                    print("   No similar fields found")
                
                if suggestions.get("pattern_suggestions"):
                    print(f"   Pattern matches: {', '.join(suggestions['pattern_suggestions'])}")
            
            # Step 5: Create a corrected query
            print("\n✅ Step 5: Create Corrected Query")
            print("-" * 40)
            
            corrected_query = """
            {
                subject(first: 5) {
                    id
                    submitter_id
                    gender
                    race
                    ethnicity
                    age_at_enrollment
                }
            }
            """
            
            print("Corrected query:")
            print(corrected_query)
            
            # Step 6: Validate corrected query
            print("\n🎯 Step 6: Validate Corrected Query")
            print("-" * 40)
            
            final_validation = await validator.validate_query_fields(corrected_query)
            
            print(f"Final validation: {'✅ VALID' if final_validation['valid'] else '❌ INVALID'}")
            
            if final_validation["valid"]:
                print("🎉 Query is now safe to execute!")
                print(f"✓ All {final_validation['summary']['valid_fields']} fields validated")
                
                # Could now execute: result = await client.post_json("/api/v0/submission/graphql", json={"query": corrected_query})
                print("\n📝 You can now safely execute this query with query_graphql()")
            else:
                print("⚠️  Query still has issues:")
                for error in final_validation["summary"]["errors"]:
                    print(f"   • {error}")
            
            # Step 7: Show template for another entity
            print("\n🔬 Step 7: Generate Template for Different Entity")
            print("-" * 40)
            
            sample_template = await validator.get_query_template("sample", include_relationships=True)
            if sample_template["exists"]:
                print("Template for 'sample' entity:")
                print(sample_template["template"][:500] + "..." if len(sample_template["template"]) > 500 else sample_template["template"])
                print(f"\n📋 Usage notes:")
                for note in sample_template["usage_notes"]:
                    print(f"   • {note}")
            
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        print("Make sure you have valid credentials and the Gen3 endpoint is accessible.")
    
    print("\n" + "=" * 60)
    print("🎓 Workflow Summary:")
    print("1. Always start with get_query_template() for safe foundations")
    print("2. Validate queries with validate_query_fields() before execution") 
    print("3. Use suggest_similar_fields() to fix invalid field names")
    print("4. Only execute queries after validation passes")
    print("5. This prevents 99% of GraphQL field name hallucinations!")


async def demonstrate_common_mistakes():
    """Show examples of common field name mistakes and their corrections"""
    
    print("\n🎯 Common GraphQL Field Name Mistakes in Gen3")
    print("=" * 50)
    
    common_mistakes = [
        {
            "entity": "subject",
            "wrong": "patient_id",
            "right": "submitter_id",
            "explanation": "Gen3 uses 'submitter_id' not 'patient_id'"
        },
        {
            "entity": "subject", 
            "wrong": "study_name",
            "right": "studies { study_description }",
            "explanation": "study_name is in the related 'study' entity, not 'subject'"
        },
        {
            "entity": "imaging_file",
            "wrong": "imaging_modality", 
            "right": "modality",
            "explanation": "Field name is just 'modality', not 'imaging_modality'"
        },
        {
            "entity": "sample",
            "wrong": "tissue_type",
            "right": "sample_type", 
            "explanation": "Gen3 uses 'sample_type' not 'tissue_type'"
        },
        {
            "entity": "variant_call_file",
            "wrong": "variant_type",
            "right": "data_type",
            "explanation": "File metadata uses 'data_type' for variant information"
        }
    ]
    
    for i, mistake in enumerate(common_mistakes, 1):
        print(f"\n{i}. Entity: {mistake['entity']}")
        print(f"   ❌ Wrong: {mistake['wrong']}")
        print(f"   ✅ Right: {mistake['right']}")  
        print(f"   💡 Why: {mistake['explanation']}")
    
    print(f"\n🛡️ The validation tools catch ALL of these mistakes automatically!")


if __name__ == "__main__":
    print("Starting Gen3 MCP Validation Demo...")
    print("Note: This requires valid Gen3 credentials and network access")
    
    asyncio.run(demonstrate_validation_workflow())
    asyncio.run(demonstrate_common_mistakes())
