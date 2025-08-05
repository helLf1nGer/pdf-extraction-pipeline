#!/usr/bin/env python
"""
Test the new enhanced model routing on first 5 PDFs.
"""

import asyncio
import logging
import json
from pathlib import Path
from src.extractors.pipeline import create_validation_pipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_batch_extraction():
    """Test the enhanced routing on first 5 PDFs."""
    
    # Test PDFs
    test_pdfs = [
        "data/1.pdf",
        "data/2.pdf", 
        "data/3.pdf",
        "data/4.pdf",
        "data/5.pdf"
    ]
    
    # Create pipeline with enhanced routing
    pipeline = create_validation_pipeline(
        mock_mode=False,
        enable_claude_fallback=True,
        confidence_threshold=70.0
    )
    
    try:
        # Validate setup
        print("Validating pipeline setup...")
        validation = await pipeline.validate_setup()
        print(f"Setup validation: {validation['overall_status']}")
        if validation['errors']:
            print(f"Errors: {validation['errors']}")
            return
        
        print("\nStarting batch extraction of 5 PDFs...")
        print("=" * 60)
        
        # Process PDFs
        results = await pipeline.batch_extract(
            test_pdfs,
            output_dir="outputs/enhanced_routing_test",
            max_concurrent=2,  # Process 2 at a time
            save_intermediate=True
        )
        
        # Analyze results
        print("\n" + "=" * 60)
        print("EXTRACTION RESULTS SUMMARY")
        print("=" * 60)
        
        successful = 0
        failed = 0
        total_issues = 0
        confidence_scores = []
        
        for i, result in enumerate(results):
            pdf_name = Path(test_pdfs[i]).name
            print(f"\n{pdf_name}:")
            print(f"  Success: {result.success}")
            
            if result.success:
                successful += 1
                if result.report:
                    issue_count = len(result.report.issues)
                    total_issues += issue_count
                    print(f"  Issues found: {issue_count}")
                    print(f"  Model used: {result.model_used}")
                    
                if result.validation_metadata:
                    vm = result.validation_metadata
                    print(f"  Confidence: {vm.confidence_score:.1f}%")
                    print(f"  Pipeline: {vm.pipeline_used}")
                    if vm.confidence_score is not None:
                        confidence_scores.append(vm.confidence_score)
            else:
                failed += 1
                print(f"  Error: {result.error_message}")
            
            print(f"  Processing time: {result.processing_time:.2f}s")
        
        # Overall statistics
        print("\n" + "=" * 60)
        print("OVERALL STATISTICS")
        print("=" * 60)
        print(f"Total PDFs processed: {len(results)}")
        print(f"Successful: {successful}/{len(results)} ({successful/len(results)*100:.0f}%)")
        print(f"Failed: {failed}")
        print(f"Total issues found: {total_issues}")
        
        if confidence_scores:
            avg_confidence = sum(confidence_scores) / len(confidence_scores)
            print(f"Average confidence: {avg_confidence:.1f}%")
            print(f"Min confidence: {min(confidence_scores):.1f}%")
            print(f"Max confidence: {max(confidence_scores):.1f}%")
        
        # Pipeline statistics
        stats = pipeline.get_pipeline_stats()
        print(f"\nPipeline usage: {stats.get('pipeline_usage', {})}")
        print(f"Validation decisions: {stats.get('validation_decisions', {})}")
        
        # Save summary
        summary = {
            "test_pdfs": test_pdfs,
            "successful": successful,
            "failed": failed,
            "total_issues": total_issues,
            "average_confidence": avg_confidence if confidence_scores else None,
            "pipeline_stats": stats
        }
        
        output_dir = Path("outputs/enhanced_routing_test")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(output_dir / "test_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        print(f"\nSummary saved to {output_dir / 'test_summary.json'}")
        
    finally:
        await pipeline.cleanup()

if __name__ == "__main__":
    asyncio.run(test_batch_extraction())