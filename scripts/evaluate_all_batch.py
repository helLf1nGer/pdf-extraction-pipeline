#!/usr/bin/env python3
"""Batch evaluation of all extracted PDFs."""

import os
import json
import glob
import subprocess
import sys

def main():
    # Find all extracted JSON files
    extracted_files = glob.glob("outputs/*_extracted.json")
    
    if not extracted_files:
        print("No extracted JSON files found in outputs/")
        return
    
    print(f"Found {len(extracted_files)} extracted files to evaluate\n")
    
    results = []
    passing = 0
    total_accuracy = 0
    
    for json_file in sorted(extracted_files):
        # Extract PDF number from filename
        pdf_num = os.path.basename(json_file).replace("_extracted.json", "")
        pdf_file = f"data/{pdf_num}.pdf"
        
        if not os.path.exists(pdf_file):
            print(f"WARNING: PDF not found for {json_file}")
            continue
        
        print(f"Evaluating {pdf_num}.pdf...")
        
        # Run evaluation
        cmd = [sys.executable, "simple_evaluation.py", "--pdf", pdf_file, "--json", json_file]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse output for accuracy
        for line in result.stdout.split('\n'):
            if "Overall accuracy:" in line:
                accuracy = float(line.split(":")[1].split("%")[0].strip())
                total_accuracy += accuracy
                if accuracy >= 85.0:
                    passing += 1
                    status = "PASS"
                else:
                    status = "FAIL"
                
                results.append({
                    'pdf': pdf_num,
                    'accuracy': accuracy,
                    'status': status
                })
                print(f"  -> {accuracy:.1f}% - {status}")
                break
    
    # Summary
    print("\n" + "="*60)
    print("BATCH EVALUATION SUMMARY")
    print("="*60)
    
    for r in sorted(results, key=lambda x: x['accuracy'], reverse=True):
        print(f"{r['pdf']:>3}.pdf: {r['accuracy']:>5.1f}% - {r['status']}")
    
    avg_accuracy = total_accuracy / len(results) if results else 0
    print(f"\nAverage Accuracy: {avg_accuracy:.1f}%")
    print(f"Passing Rate: {passing}/{len(results)} ({passing/len(results)*100:.1f}%)")
    print("="*60)

if __name__ == "__main__":
    main()