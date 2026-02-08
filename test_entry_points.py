"""
Test script for entry point detection workflow.

This script tests the complete workflow:
1. Create a repository
2. Wait for parsing to complete
3. Detect entry points
4. Query entry points
"""

import asyncio
import httpx
import time
from pathlib import Path

BASE_URL = "http://localhost:8000/api/v1"


async def test_workflow():
    """Test the complete entry point detection workflow."""
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("=" * 70)
        print("ENTRY POINT DETECTION WORKFLOW TEST")
        print("=" * 70)
        
        # Step 1: Create a repository (use this repo as test)
        print("\n📁 Step 1: Creating repository...")
        repo_path = str(Path.cwd())
        
        create_response = await client.post(
            f"{BASE_URL}/repos",
            json={
                "path": repo_path,
                "name": "code-parser-test"
            }
        )
        
        if create_response.status_code == 409:
            # Repository already exists, get it
            print("   Repository already exists, fetching...")
            repos_response = await client.get(f"{BASE_URL}/repos")
            repos = repos_response.json()
            repo = next((r for r in repos if r["root_path"] == repo_path), None)
            if not repo:
                print("   ❌ Could not find repository")
                return
            repo_id = repo["id"]
        else:
            create_response.raise_for_status()
            repo = create_response.json()
            repo_id = repo["id"]
        
        print(f"   ✅ Repository ID: {repo_id}")
        print(f"   Name: {repo['name']}")
        print(f"   Status: {repo['status']}")
        
        # Step 2: Check/wait for parsing to complete
        print("\n⏳ Step 2: Waiting for parsing to complete...")
        max_wait = 120  # 2 minutes max
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status_response = await client.get(f"{BASE_URL}/repos/{repo_id}")
            status_response.raise_for_status()
            repo_status = status_response.json()
            
            print(f"   Status: {repo_status['status']} "
                  f"({repo_status['parsed_files']}/{repo_status['total_files']} files)")
            
            if repo_status["status"] == "completed":
                print("   ✅ Parsing completed!")
                print(f"   Languages: {repo_status.get('languages', [])}")
                break
            elif repo_status["status"] == "failed":
                print(f"   ❌ Parsing failed: {repo_status.get('error_message')}")
                return
            
            await asyncio.sleep(2)
        else:
            print("   ⏰ Timeout waiting for parsing to complete")
            return
        
        # Step 3: Detect entry points
        print("\n🔍 Step 3: Detecting entry points...")
        
        detect_response = await client.post(
            f"{BASE_URL}/repos/{repo_id}/entry-points/detect",
            json={
                "min_confidence": 0.6,
                "force_redetect": True  # Force re-detect for testing
            }
        )
        detect_response.raise_for_status()
        detection_result = detect_response.json()
        
        print(f"   ✅ Detection complete!")
        print(f"   Languages detected: {detection_result['languages_detected']}")
        print(f"   Total candidates found: {detection_result['total_candidates_found']}")
        print(f"   Entry points stored: {detection_result['entry_points_stored']}")
        print(f"   Candidates stored: {detection_result['candidates_stored']}")
        
        # Show statistics
        stats = detection_result['statistics']
        print(f"\n   📊 Statistics:")
        print(f"      By Type:")
        for entry_type, count in stats['by_type'].items():
            if count > 0:
                print(f"         {entry_type}: {count}")
        
        print(f"      By Confidence:")
        for level, count in stats['by_confidence'].items():
            if count > 0:
                print(f"         {level}: {count}")
        
        # Step 4: Get detection status
        print("\n📊 Step 4: Getting detection status...")
        
        status_response = await client.get(
            f"{BASE_URL}/repos/{repo_id}/entry-points/status"
        )
        status_response.raise_for_status()
        status = status_response.json()
        
        print(f"   Entry points count: {status['entry_points_count']}")
        print(f"   Candidates count: {status['candidates_count']}")
        print(f"   Languages: {status['languages']}")
        
        # Step 5: Query entry points
        print("\n📋 Step 5: Querying entry points...")
        
        endpoints_response = await client.get(
            f"{BASE_URL}/repos/{repo_id}/entry-points?limit=20"
        )
        endpoints_response.raise_for_status()
        endpoints = endpoints_response.json()
        
        print(f"   Found {len(endpoints)} entry points:")
        print()
        
        # Group by type
        by_type = {}
        for ep in endpoints:
            entry_type = ep['entry_type']
            if entry_type not in by_type:
                by_type[entry_type] = []
            by_type[entry_type].append(ep)
        
        # Show first few of each type
        for entry_type, eps in by_type.items():
            print(f"   {entry_type.upper()} Entry Points:")
            for ep in eps[:5]:  # Show first 5
                method = ep.get('method', '')
                path = ep.get('path', '')
                framework = ep.get('framework', 'unknown')
                confidence = ep.get('confidence', 0)
                
                if method and path:
                    print(f"      • {method} {path} ({framework}, {confidence:.0%})")
                else:
                    print(f"      • {ep.get('trigger_description', 'Unknown')} "
                          f"({framework}, {confidence:.0%})")
            
            if len(eps) > 5:
                print(f"      ... and {len(eps) - 5} more")
            print()
        
        # Step 6: Get summary
        print("📈 Step 6: Getting summary...")
        
        summary_response = await client.get(
            f"{BASE_URL}/repos/{repo_id}/entry-points/summary"
        )
        summary_response.raise_for_status()
        summary = summary_response.json()
        
        print(f"   Total entry points: {summary['total_entry_points']}")
        print(f"   Average confidence: {summary['average_confidence']:.1%}")
        print(f"\n   By Framework:")
        for framework, count in sorted(
            summary['by_framework'].items(), 
            key=lambda x: x[1], 
            reverse=True
        ):
            print(f"      {framework}: {count}")
        
        print("\n" + "=" * 70)
        print("✅ TEST COMPLETE!")
        print("=" * 70)
        print(f"\n🔗 View in browser:")
        print(f"   Docs: http://localhost:8000/docs")
        print(f"   Repo: http://localhost:8000/api/v1/repos/{repo_id}")
        print(f"   Entry Points: http://localhost:8000/api/v1/repos/{repo_id}/entry-points")


if __name__ == "__main__":
    try:
        asyncio.run(test_workflow())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

