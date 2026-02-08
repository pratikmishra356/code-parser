"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_python_code() -> str:
    """Sample Python code for testing parsers."""
    return '''
"""Sample module for testing."""

import os
from pathlib import Path


class BaseProcessor:
    """Base class for processors."""
    
    def process(self, data: str) -> str:
        raise NotImplementedError


class DataProcessor(BaseProcessor):
    """Processes data."""
    
    def __init__(self, config: dict):
        self.config = config
    
    def process(self, data: str) -> str:
        """Process the input data."""
        cleaned = self._clean(data)
        return self._transform(cleaned)
    
    def _clean(self, data: str) -> str:
        return data.strip()
    
    def _transform(self, data: str) -> str:
        return data.upper()


def main():
    """Entry point."""
    processor = DataProcessor({"key": "value"})
    result = processor.process("  hello world  ")
    print(result)


if __name__ == "__main__":
    main()
'''


@pytest.fixture
def sample_java_code() -> str:
    """Sample Java code for testing parsers."""
    return '''
package com.example;

import java.util.List;
import java.util.ArrayList;

public class DataService {
    private final Repository repository;
    
    public DataService(Repository repository) {
        this.repository = repository;
    }
    
    public List<String> fetchAll() {
        List<String> results = new ArrayList<>();
        for (String item : repository.getItems()) {
            results.add(process(item));
        }
        return results;
    }
    
    private String process(String item) {
        return item.toUpperCase();
    }
}
'''


@pytest.fixture
def sample_javascript_code() -> str:
    """Sample JavaScript code for testing parsers."""
    return '''
import { fetchData } from './api';
import { processItem } from './utils';

class DataManager {
    constructor(config) {
        this.config = config;
    }
    
    async loadData() {
        const data = await fetchData(this.config.endpoint);
        return data.map(item => processItem(item));
    }
}

const formatResult = (result) => {
    return JSON.stringify(result, null, 2);
};

export { DataManager, formatResult };
'''


@pytest.fixture
def sample_rust_code() -> str:
    """Sample Rust code for testing parsers."""
    return '''
use std::collections::HashMap;

pub struct Config {
    pub name: String,
    pub values: HashMap<String, i32>,
}

impl Config {
    pub fn new(name: &str) -> Self {
        Config {
            name: name.to_string(),
            values: HashMap::new(),
        }
    }
    
    pub fn get(&self, key: &str) -> Option<&i32> {
        self.values.get(key)
    }
}

pub fn process_config(config: &Config) -> String {
    format!("Config: {}", config.name)
}

fn main() {
    let config = Config::new("test");
    let result = process_config(&config);
    println!("{}", result);
}
'''

