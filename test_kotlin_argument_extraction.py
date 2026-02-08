"""Test Kotlin parser argument extraction for Camel routes."""

import asyncio
from pathlib import Path

from code_parser.parsers.kotlin_parser import KotlinParser


async def test_camel_route_parsing():
    """Test parsing a Camel route with processor arguments."""
    
    # Sample Camel route code
    camel_route_code = """
package com.toasttab.pipeline.paymentfraudchecker.route.fraud

import org.apache.camel.builder.RouteBuilder
import com.toasttab.pipeline.paymentfraudchecker.processor.UnlinkedRefundFraudProcessor
import com.toasttab.pipeline.paymentfraudchecker.predicate.UnlinkedRefundPredicate
import javax.inject.Inject

class UnlinkedRefundFraudCheckerRoute @Inject constructor(
    private val unlinkedRefundFraudProcessor: UnlinkedRefundFraudProcessor,
    private val unlinkedRefundPredicate: UnlinkedRefundPredicate
) : RouteBuilder() {
    
    override fun configure() {
        from(RouteId.UNLINKED_REFUND_FRAUD_CHECKER_ROUTE.directUri())
            .routeId(RouteId.UNLINKED_REFUND_FRAUD_CHECKER_ROUTE.id)
            .filter(unlinkedRefundPredicate)
            .process(unlinkedRefundFraudProcessor)
            .to(UnlinkedRefundFraudProducerRoute.RouteId.UNLINKED_REFUND_FRAUD_PRODUCER_ROUTE.directUri())
            .end()
    }
}
"""
    
    parser = KotlinParser()
    result = parser.parse(
        source_code=camel_route_code,
        file_path="com/toasttab/pipeline/paymentfraudchecker/route/fraud/UnlinkedRefundFraudCheckerRoute.kt",
        content_hash="test_hash_123"
    )
    
    print("=" * 80)
    print("PARSE RESULTS")
    print("=" * 80)
    print(f"Symbols: {len(result.symbols)}")
    print(f"References: {len(result.references)}")
    print()
    
    print("SYMBOLS:")
    for sym in result.symbols:
        print(f"  - {sym.name} ({sym.kind})")
    print()
    
    print("REFERENCES:")
    for ref in result.references:
        print(f"  - {ref.source_symbol_name} -> {ref.target_symbol_name}")
        print(f"    type: {ref.reference_type}, target_path: {ref.target_file_path}")
    print()
    
    # Check if we found the processor references
    processor_refs = [
        r for r in result.references 
        if "Processor" in r.target_symbol_name or "Predicate" in r.target_symbol_name
    ]
    
    if processor_refs:
        print(f"✅ SUCCESS! Found {len(processor_refs)} processor/predicate references:")
        for ref in processor_refs:
            print(f"   - {ref.target_symbol_name} (from {ref.source_symbol_name})")
    else:
        print("❌ FAIL: No processor/predicate references found")
        print("   Expected: UnlinkedRefundFraudProcessor, UnlinkedRefundPredicate")


if __name__ == "__main__":
    asyncio.run(test_camel_route_parsing())
