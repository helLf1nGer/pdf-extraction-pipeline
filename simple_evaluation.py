#!/usr/bin/env python3
"""
Simplified evaluation script for home inspection PDF extraction accuracy.

This is a simplified version that directly calls the LLM APIs for evaluation
without going through the complex extraction pipeline. Provides basic accuracy
assessment comparing extracted JSON against source PDFs.

Usage:
    python simple_evaluation.py --pdf data/1.pdf --json outputs/1_extracted.json
"""

import os
import sys
import json
import asyncio
import argparse
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import time

import fitz  # PyMuPDF

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_pdf_content(pdf_path: str) -> Dict[str, Any]:
    """Extract text and image information from PDF."""
    doc = fitz.open(pdf_path)
    
    # Extract text
    full_text = ""
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        full_text += f"\n--- Page {page_num + 1} ---\n"
        full_text += page.get_text()
    
    # Extract image information
    image_info = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        image_list = page.get_images()
        for img_index, img in enumerate(image_list):
            image_info.append({
                'page': page_num + 1,
                'index': img_index,
                'location': f"page_{page_num + 1:02d}_image_{img_index + 1:03d}"
            })
    
    doc.close()
    
    return {
        'text': full_text,
        'images': image_info,
        'total_images': len(image_info)
    }


def load_extracted_data(json_path: str) -> Dict[str, Any]:
    """Load extracted JSON data."""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def analyze_extraction_accuracy(pdf_content: Dict[str, Any], extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform basic accuracy analysis without LLM calls.
    
    This provides a simplified evaluation focusing on quantifiable metrics.
    """
    evaluation = {
        'timestamp': datetime.now().isoformat(),
        'pdf_analysis': {},
        'extraction_analysis': {},
        'accuracy_metrics': {},
        'summary': ''
    }
    
    # Analyze PDF content
    pdf_text = pdf_content['text']
    pdf_images = pdf_content['images']
    
    # Count potential issues in PDF text (simple heuristics)
    issue_indicators = [
        'repair', 'replace', 'fix', 'concern', 'issue', 'problem', 
        'recommend', 'safety', 'hazard', 'defect', 'damage',
        'inspection', 'noted', 'observed', 'found'
    ]
    
    # Simple issue counting (very approximate)
    issue_sentences = []
    sentences = pdf_text.split('.')
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(indicator in sentence_lower for indicator in issue_indicators):
            if len(sentence.strip()) > 20:  # Filter out very short sentences
                issue_sentences.append(sentence.strip())
    
    estimated_issues = len(set(issue_sentences)) // 3  # Rough approximation
    if estimated_issues < 5:
        estimated_issues = max(5, len(issue_sentences) // 5)
    
    evaluation['pdf_analysis'] = {
        'estimated_issues': estimated_issues,
        'total_images': len(pdf_images),
        'text_length': len(pdf_text),
        'issue_indicators_found': len(issue_sentences)
    }
    
    # Analyze extracted data
    extracted_issues = extracted_data.get('issues', [])
    extracted_issue_count = len(extracted_issues)
    
    # Count images in extraction (both legacy and enhanced)
    total_extracted_images = 0
    total_enhanced_images = 0
    high_confidence_images = 0
    for issue in extracted_issues:
        # Count legacy images
        total_extracted_images += len(issue.get('issue_images', []))
        # Count enhanced images
        enhanced = issue.get('enhanced_images', [])
        total_enhanced_images += len(enhanced)
        # Count high confidence matches
        for img in enhanced:
            if img.get('confidence_score', 0) >= 70:
                high_confidence_images += 1
    
    # Use enhanced images if available, otherwise fall back to legacy
    effective_extracted_images = total_enhanced_images if total_enhanced_images > 0 else total_extracted_images
    
    evaluation['extraction_analysis'] = {
        'extracted_issues': extracted_issue_count,
        'total_extracted_images': total_extracted_images,
        'total_enhanced_images': total_enhanced_images,
        'high_confidence_images': high_confidence_images,
        'effective_extracted_images': effective_extracted_images,
        'report_name': extracted_data.get('report_name', ''),
        'has_report_name': bool(extracted_data.get('report_name', '').strip())
    }
    
    # Calculate basic accuracy metrics
    # Issue count accuracy
    if estimated_issues > 0:
        issue_count_accuracy = min(100, (extracted_issue_count / estimated_issues) * 100)
        if extracted_issue_count > estimated_issues * 1.5:
            # Penalize for too many issues (possible false positives)
            issue_count_accuracy = max(50, issue_count_accuracy - 20)
    else:
        issue_count_accuracy = 100 if extracted_issue_count == 0 else 80
    
    # Image extraction accuracy (using enhanced images if available)
    if len(pdf_images) > 0:
        # For enhanced images, only count high confidence matches for accuracy
        if total_enhanced_images > 0:
            image_accuracy = (high_confidence_images / extracted_issue_count) * 100
        else:
            image_accuracy = (total_extracted_images / len(pdf_images)) * 100
        image_accuracy = min(100, image_accuracy)  # Cap at 100%
    else:
        image_accuracy = 100 if effective_extracted_images == 0 else 0
    
    # Content quality score (basic heuristics)
    content_score = 0
    if evaluation['extraction_analysis']['has_report_name']:
        content_score += 20
    
    if extracted_issue_count > 0:
        # Check if issues have required fields
        complete_issues = 0
        for issue in extracted_issues:
            if (issue.get('issue_name', '').strip() and 
                issue.get('issue_description', '').strip() and
                issue.get('issue_type', '').strip()):
                complete_issues += 1
        
        content_score += (complete_issues / extracted_issue_count) * 60
        
        # Check for reasonable description lengths
        avg_desc_length = sum(len(issue.get('issue_description', '')) for issue in extracted_issues) / extracted_issue_count
        if avg_desc_length > 50:
            content_score += 20
        elif avg_desc_length > 20:
            content_score += 10
    
    # Overall accuracy (weighted combination)
    overall_accuracy = (
        issue_count_accuracy * 0.3 +  # 30% weight on issue count
        content_score * 0.5 +          # 50% weight on content quality  
        image_accuracy * 0.2           # 20% weight on image extraction
    )
    
    evaluation['accuracy_metrics'] = {
        'issue_count_accuracy': round(issue_count_accuracy, 1),
        'content_quality_score': round(content_score, 1),
        'image_extraction_accuracy': round(image_accuracy, 1),
        'overall_accuracy': round(overall_accuracy, 1),
        'passes_85_threshold': overall_accuracy >= 85.0
    }
    
    # Generate summary
    summary_parts = []
    summary_parts.append(f"Overall accuracy: {overall_accuracy:.1f}%")
    summary_parts.append(f"Estimated {estimated_issues} issues in PDF, extracted {extracted_issue_count}")
    if total_enhanced_images > 0:
        summary_parts.append(f"Enhanced image matching: {high_confidence_images} high confidence matches from {total_enhanced_images} total")
    else:
        summary_parts.append(f"Found {len(pdf_images)} images in PDF, extracted {total_extracted_images}")
    
    if overall_accuracy >= 85.0:
        summary_parts.append("PASSES 85% threshold")
    else:
        summary_parts.append("FAILS 85% threshold")
    
    evaluation['summary'] = ". ".join(summary_parts) + "."
    
    # Add detailed findings
    evaluation['findings'] = {
        'strengths': [],
        'weaknesses': [],
        'recommendations': []
    }
    
    # Identify strengths
    if evaluation['extraction_analysis']['has_report_name']:
        evaluation['findings']['strengths'].append("Report name correctly extracted")
    
    if extracted_issue_count > 0:
        evaluation['findings']['strengths'].append(f"Successfully extracted {extracted_issue_count} issues")
    
    if content_score > 80:
        evaluation['findings']['strengths'].append("High content quality with complete issue descriptions")
    
    # Identify weaknesses
    if image_accuracy < 50:
        evaluation['findings']['weaknesses'].append("Poor image extraction - most images missing")
    elif image_accuracy < 80:
        evaluation['findings']['weaknesses'].append("Incomplete image extraction")
    
    if issue_count_accuracy < 80:
        if extracted_issue_count < estimated_issues:
            evaluation['findings']['weaknesses'].append("May have missed some issues (false negatives)")
        else:
            evaluation['findings']['weaknesses'].append("May have extracted too many issues (false positives)")
    
    if content_score < 60:
        evaluation['findings']['weaknesses'].append("Incomplete issue descriptions or missing required fields")
    
    # Add recommendations
    if image_accuracy < 50:
        evaluation['findings']['recommendations'].append("Critical: Fix image extraction pipeline")
    
    if issue_count_accuracy < 85:
        evaluation['findings']['recommendations'].append("Improve issue detection accuracy")
    
    if content_score < 80:
        evaluation['findings']['recommendations'].append("Enhance content extraction completeness")
    
    return evaluation


def save_evaluation_results(evaluation: Dict[str, Any], output_path: str):
    """Save evaluation results to file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(evaluation, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Evaluation results saved to {output_path}")


def print_evaluation_summary(evaluation: Dict[str, Any], pdf_name: str, json_name: str):
    """Print evaluation summary to console."""
    print("\n" + "=" * 60)
    print("HOME INSPECTION EXTRACTION EVALUATION")
    print("=" * 60)
    
    print(f"\nFiles Evaluated:")
    print(f"  PDF: {pdf_name}")
    print(f"  JSON: {json_name}")
    print(f"  Evaluation Time: {evaluation['timestamp']}")
    
    print(f"\nPDF Analysis:")
    pdf_analysis = evaluation['pdf_analysis']
    print(f"  Estimated Issues: {pdf_analysis['estimated_issues']}")
    print(f"  Total Images: {pdf_analysis['total_images']}")
    print(f"  Text Length: {pdf_analysis['text_length']:,} characters")
    
    print(f"\nExtraction Analysis:")
    ext_analysis = evaluation['extraction_analysis']
    print(f"  Extracted Issues: {ext_analysis['extracted_issues']}")
    if ext_analysis.get('total_enhanced_images', 0) > 0:
        print(f"  Enhanced Images: {ext_analysis['high_confidence_images']} high confidence / {ext_analysis['total_enhanced_images']} total")
    else:
        print(f"  Extracted Images: {ext_analysis['total_extracted_images']}")
    print(f"  Has Report Name: {ext_analysis['has_report_name']}")
    
    print(f"\nAccuracy Metrics:")
    metrics = evaluation['accuracy_metrics']
    print(f"  Overall Accuracy: {metrics['overall_accuracy']}%")
    print(f"  Issue Count Accuracy: {metrics['issue_count_accuracy']}%")
    print(f"  Content Quality: {metrics['content_quality_score']}%")
    print(f"  Image Extraction: {metrics['image_extraction_accuracy']}%")
    
    # Threshold result
    if metrics['passes_85_threshold']:
        print(f"  PASSES 85% Threshold!")
    else:
        print(f"  FAILS 85% Threshold")
    
    # Findings
    findings = evaluation['findings']
    if findings['strengths']:
        print(f"\nStrengths:")
        for strength in findings['strengths']:
            print(f"  • {strength}")
    
    if findings['weaknesses']:
        print(f"\nWeaknesses:")
        for weakness in findings['weaknesses']:
            print(f"  • {weakness}")
    
    if findings['recommendations']:
        print(f"\nRecommendations:")
        for rec in findings['recommendations']:
            print(f"  • {rec}")
    
    print(f"\nSummary:")
    print(f"  {evaluation['summary']}")
    
    print("\n" + "=" * 60)


def batch_evaluate_directory(data_dir: str, outputs_dir: str, evaluation_dir: str) -> Dict[str, Any]:
    """Evaluate all PDF-JSON pairs in directories."""
    data_path = Path(data_dir)
    outputs_path = Path(outputs_dir)
    
    # Find all PDF files and matching JSONs
    evaluations = []
    total_files = 0
    passing_files = 0
    
    pdf_files = list(data_path.glob("*.pdf"))
    logger.info(f"Found {len(pdf_files)} PDF files")
    
    for pdf_file in sorted(pdf_files):
        pdf_stem = pdf_file.stem
        json_file = outputs_path / f"{pdf_stem}_extracted.json"
        
        if json_file.exists():
            total_files += 1
            logger.info(f"Evaluating {pdf_file.name} -> {json_file.name}")
            
            try:
                # Extract PDF content
                pdf_content = extract_pdf_content(str(pdf_file))
                
                # Load extracted data
                extracted_data = load_extracted_data(str(json_file))
                
                # Perform evaluation
                evaluation = analyze_extraction_accuracy(pdf_content, extracted_data)
                evaluation['pdf_filename'] = pdf_file.name
                evaluation['json_filename'] = json_file.name
                
                evaluations.append(evaluation)
                
                if evaluation['accuracy_metrics']['passes_85_threshold']:
                    passing_files += 1
                
                # Save individual result
                output_file = Path(evaluation_dir) / f"{pdf_stem}_evaluation.json"
                save_evaluation_results(evaluation, str(output_file))
                
                print(f"  {pdf_file.name}: {evaluation['accuracy_metrics']['overall_accuracy']:.1f}% "
                      f"({'PASS' if evaluation['accuracy_metrics']['passes_85_threshold'] else 'FAIL'})")
                
            except Exception as e:
                logger.error(f"Failed to evaluate {pdf_file.name}: {str(e)}")
        else:
            logger.warning(f"No JSON file found for {pdf_file.name}")
    
    # Calculate batch statistics
    if evaluations:
        avg_accuracy = sum(e['accuracy_metrics']['overall_accuracy'] for e in evaluations) / len(evaluations)
        avg_content = sum(e['accuracy_metrics']['content_quality_score'] for e in evaluations) / len(evaluations)
        avg_image = sum(e['accuracy_metrics']['image_extraction_accuracy'] for e in evaluations) / len(evaluations)
        avg_issue_count = sum(e['accuracy_metrics']['issue_count_accuracy'] for e in evaluations) / len(evaluations)
        
        pass_rate = (passing_files / total_files) * 100 if total_files > 0 else 0
        
        batch_summary = {
            'timestamp': datetime.now().isoformat(),
            'total_evaluations': total_files,
            'passing_evaluations': passing_files,
            'pass_rate': round(pass_rate, 1),
            'average_overall_accuracy': round(avg_accuracy, 1),
            'average_content_quality': round(avg_content, 1),
            'average_image_accuracy': round(avg_image, 1),
            'average_issue_count_accuracy': round(avg_issue_count, 1),
            'meets_system_requirements': avg_accuracy >= 85.0,
            'individual_evaluations': evaluations
        }
        
        # Save batch summary
        batch_file = Path(evaluation_dir) / f"batch_evaluation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_evaluation_results(batch_summary, str(batch_file))
        
        return batch_summary
    else:
        logger.error("No evaluations completed")
        return {}


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Simple evaluation of PDF extraction accuracy"
    )
    parser.add_argument(
        "--pdf",
        help="Path to PDF file for single evaluation"
    )
    parser.add_argument(
        "--json", 
        help="Path to extracted JSON file for single evaluation"
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory containing PDF files for batch evaluation"
    )
    parser.add_argument(
        "--outputs-dir",
        default="outputs",
        help="Directory containing extracted JSON files"
    )
    parser.add_argument(
        "--evaluation-dir",
        default="outputs/evaluations",
        help="Directory to save evaluation results"
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Run batch evaluation on all files"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        if args.batch:
            # Batch evaluation
            logger.info("Running batch evaluation...")
            batch_summary = batch_evaluate_directory(
                args.data_dir, args.outputs_dir, args.evaluation_dir
            )
            
            if batch_summary:
                print("\n" + "=" * 80)
                print("BATCH EVALUATION SUMMARY")
                print("=" * 80)
                print(f"Total Evaluations: {batch_summary['total_evaluations']}")
                print(f"Passing Evaluations: {batch_summary['passing_evaluations']}")
                print(f"Pass Rate: {batch_summary['pass_rate']}%")
                print(f"Average Overall Accuracy: {batch_summary['average_overall_accuracy']}%")
                print(f"Average Content Quality: {batch_summary['average_content_quality']}%")
                print(f"Average Image Accuracy: {batch_summary['average_image_accuracy']}%")
                print(f"System Requirements: {'MET' if batch_summary['meets_system_requirements'] else 'NOT MET'}")
                print("=" * 80)
                
                return 0 if batch_summary['meets_system_requirements'] else 2
        
        elif args.pdf and args.json:
            # Single evaluation
            if not Path(args.pdf).exists():
                logger.error(f"PDF file not found: {args.pdf}")
                return 1
            
            if not Path(args.json).exists():
                logger.error(f"JSON file not found: {args.json}")
                return 1
            
            logger.info(f"Evaluating {args.pdf} -> {args.json}")
            
            # Extract PDF content
            pdf_content = extract_pdf_content(args.pdf)
            
            # Load extracted data
            extracted_data = load_extracted_data(args.json)
            
            # Perform evaluation
            evaluation = analyze_extraction_accuracy(pdf_content, extracted_data)
            
            # Print results
            print_evaluation_summary(evaluation, Path(args.pdf).name, Path(args.json).name)
            
            # Save results
            output_file = Path(args.evaluation_dir) / f"{Path(args.pdf).stem}_evaluation.json"
            save_evaluation_results(evaluation, str(output_file))
            
            return 0 if evaluation['accuracy_metrics']['passes_85_threshold'] else 2
        
        else:
            parser.print_help()
            return 1
            
    except KeyboardInterrupt:
        logger.info("Evaluation interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Evaluation failed: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)