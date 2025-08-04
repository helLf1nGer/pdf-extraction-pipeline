import os
import glob

def get_all_sec_filings(ticker: str) -> str:
    file_contents = ''
    script_dir = os.path.dirname(os.path.abspath(__file__))
    files = glob.glob(f'{script_dir}/data/{ticker}/*.txt')
    for file in files:
        with open(file, 'r') as f:
            file_contents += f.read()
    return file_contents

def get_yearly_report(ticker: str) -> str:
    file_contents = ''
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pattern = f'{script_dir}/data/{ticker}/{ticker}_10K_*.txt'
    files = glob.glob(pattern)
    
    for file in files:
        with open(file, 'r') as f:
            file_contents += f.read()
    return file_contents

def get_quaterly_report(ticker: str) -> dict:
    file_contents = ''
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pattern = f'{script_dir}/data/{ticker}/{ticker}_10Q_*.txt'
    files = glob.glob(pattern)
    
    for file in files:
        with open(file, 'r') as f:
            file_contents += f.read()
    return file_contents

def get_sec_filings(ticker: str) -> dict:
    file_contents = {}
    file_contents['10K'] = get_yearly_report(ticker)
    file_contents['10Q'] = get_quaterly_report(ticker)
    return file_contents
    
if __name__ == '__main__':
    print(get_sec_filings('AAPL'))
