#!/usr/bin/env python3
"""Analyze entry point candidates to identify real entry points."""

import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from code_parser.database.models import FileModel, EntryPointCandidateModel
from code_parser.database.connection import get_database_url

REPO_ID = "01KG9VVSE5CV4HCTET1MP1XC1J"


async def analyze_candidates():
    """Analyze all candidates and determine which are real entry points."""
    database_url = str(get_database_url())
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    entry_points_found = []
    non_entry_points = []
    
    async with async_session() as session:
        # Get all candidates for this repo
        result = await session.execute(
            select(EntryPointCandidateModel).where(
                EntryPointCandidateModel.repo_id == REPO_ID
            )
        )
        candidates = result.scalars().all()
        
        # Group by file_id
        file_candidates = {}
        for cand in candidates:
            fid = cand.file_id
            if fid not in file_candidates:
                file_candidates[fid] = []
            file_candidates[fid].append(cand)
        
        print(f"Found {len(file_candidates)} unique files with {len(candidates)} total candidates\n")
        
        # Analyze each file
        for fid, cands in sorted(file_candidates.items()):
            # Get file from database
            file_result = await session.execute(
                select(FileModel).where(FileModel.id == fid)
            )
            file_model = file_result.scalar_one_or_none()
            
            if not file_model:
                print(f"\n❌ File not found: {fid}")
                continue
            
            path = file_model.relative_path
            content = file_model.content or ""
            patterns = [c.detection_pattern for c in cands]
            
            print(f"\n{'='*80}")
            print(f"File: {path}")
            print(f"Patterns: {', '.join(set(patterns))}")
            print(f"Candidates: {len(cands)}")
            
            # Check for entry point indicators
            has_pulsar = 'pulsar://' in content
            has_kafka = 'kafka://' in content
            has_http = 'netty-http://' in content or 'netty-https://' in content
            has_timer = 'timer://' in content or 'cron://' in content
            has_direct = 'direct://' in content
            has_seda = 'seda://' in content
            has_from = 'from(' in content.lower()
            
            # Check if it's a base class or test
            is_test = 'test' in path.lower() or 'spec' in path.lower()
            is_base = 'base' in path.lower() or 'abstract' in path.lower()
            is_module = 'module' in path.lower() or 'config' in path.lower()
            
            # Determine if it's an entry point
            is_entry_point = False
            entry_type = None
            reasons = []
            
            if has_pulsar or has_kafka or has_http or has_timer:
                is_entry_point = True
                if has_pulsar or has_kafka:
                    entry_type = "EVENT"
                    reasons.append("✅ External message queue (pulsar/kafka)")
                elif has_http:
                    entry_type = "HTTP"
                    reasons.append("✅ HTTP endpoint")
                elif has_timer:
                    entry_type = "SCHEDULER"
                    reasons.append("✅ Timer/cron scheduler")
            
            if is_test:
                reasons.append("⚠️  TEST FILE")
                is_entry_point = False
            if is_base:
                reasons.append("⚠️  BASE CLASS")
                is_entry_point = False
            if is_module and not (has_pulsar or has_kafka or has_http or has_timer):
                reasons.append("⚠️  MODULE/CONFIG (no external endpoints)")
                is_entry_point = False
            
            if has_direct and not (has_pulsar or has_kafka or has_http or has_timer):
                reasons.append("⚠️  Only internal routing (direct://)")
                is_entry_point = False
            
            if is_entry_point:
                print(f"✅ ENTRY POINT ({entry_type})")
                entry_points_found.append({
                    'path': path,
                    'type': entry_type,
                    'reasons': reasons,
                    'indicators': {
                        'pulsar': has_pulsar,
                        'kafka': has_kafka,
                        'http': has_http,
                        'timer': has_timer
                    }
                })
            else:
                print(f"❌ NOT AN ENTRY POINT")
                non_entry_points.append({
                    'path': path,
                    'reasons': reasons,
                    'has_from': has_from,
                    'has_direct': has_direct,
                    'has_seda': has_seda
                })
            
            if reasons:
                for reason in reasons:
                    print(f"  {reason}")
            
            # Show key lines with from() calls
            if has_from:
                lines = content.split('\n')
                from_lines = []
                for i, line in enumerate(lines):
                    if 'from(' in line.lower():
                        from_lines.append((i, line))
                
                if from_lines:
                    print(f"\n  Found {len(from_lines)} from() call(s):")
                    for i, line in from_lines[:3]:  # Show first 3
                        start = max(0, i-2)
                        end = min(len(lines), i+10)
                        print(f"\n  Context around line {i+1}:")
                        for j in range(start, end):
                            marker = ">>>" if j == i else "   "
                            print(f"  {marker} {j+1:4d}: {lines[j]}")
    
    print(f"\n\n{'='*80}")
    print(f"SUMMARY")
    print(f"{'='*80}")
    print(f"\n✅ Entry Points Found: {len(entry_points_found)}")
    for ep in entry_points_found:
        print(f"\n  - {ep['path']} ({ep['type']})")
        for reason in ep['reasons']:
            if reason.startswith('✅'):
                print(f"    {reason}")
        indicators = [k for k, v in ep['indicators'].items() if v]
        if indicators:
            print(f"    Indicators: {', '.join(indicators)}")
    
    print(f"\n❌ Non-Entry Points: {len(non_entry_points)}")
    for nep in non_entry_points:
        print(f"\n  - {nep['path']}")
        for reason in nep['reasons']:
            print(f"    {reason}")
        if nep['has_direct']:
            print(f"    Has direct:// routing (internal only)")
        if nep['has_seda']:
            print(f"    Has seda:// routing (internal only)")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(analyze_candidates())
