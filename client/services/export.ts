/**
 * Export Service - Handles exporting questions in various formats
 */

import { Platform } from 'react-native';
import { Paths, File } from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import * as XLSX from 'xlsx';
import { Question } from './questions';

/** Trigger a download in the browser via a temporary anchor element. */
const webDownload = (data: Uint8Array | string, filename: string, mimeType: string) => {
  const blob = typeof data === 'string'
    ? new Blob([data], { type: mimeType })
    : new Blob([data], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

export type ExportFormat = 'xlsx' | 'csv' | 'docx';

export interface ExportOptions {
  format: ExportFormat;
  includeReplacedQuestions?: boolean;
  groupBy?: 'none' | 'chapter' | 'subject' | 'type' | 'difficulty';
  filterVettingStatus?: 'all' | 'approved' | 'pending' | 'rejected';
}

export interface ExportResult {
  success: boolean;
  filePath?: string;
  error?: string;
}

/**
 * Format question data for export
 */
const formatQuestionForExport = (q: Question, index: number) => ({
  'S.No': index + 1,
  'Question': q.question_text,
  'Type': q.question_type?.toUpperCase() || '',
  'Marks': q.marks || '',
  'Difficulty': q.difficulty_level || '',
  'Bloom Level': q.bloom_taxonomy_level || '',
  'Options': q.options?.join('\n') || '',
  'Correct Answer': q.correct_answer || '',
  'Explanation': q.explanation || '',
  'Topic Tags': q.topic_tags?.join(', ') || '',
  'Vetting Status': q.vetting_status || '',
  'Vetting Notes': q.vetting_notes || '',
  'Learning Outcome': (q as any).learning_outcome_id || '',
  'Course Outcomes': q.course_outcome_mapping ? Object.keys(q.course_outcome_mapping).join(', ') : '',
});

/**
 * Group questions by specified criteria
 */
const groupQuestions = (
  questions: Question[],
  groupBy: ExportOptions['groupBy']
): Record<string, Question[]> => {
  if (groupBy === 'none' || !groupBy) {
    return { 'All Questions': questions };
  }

  return questions.reduce((acc, q) => {
    let key: string;
    switch (groupBy) {
      case 'chapter':
        key = q.topic_tags?.[0] || 'Uncategorized';
        break;
      case 'subject':
        key = q.subject_id || 'No Subject';
        break;
      case 'type':
        key = q.question_type?.toUpperCase() || 'Unknown Type';
        break;
      case 'difficulty':
        key = q.difficulty_level || 'No Difficulty';
        break;
      default:
        key = 'All';
    }
    if (!acc[key]) acc[key] = [];
    acc[key].push(q);
    return acc;
  }, {} as Record<string, Question[]>);
};

/**
 * Generate Excel workbook
 */
const generateExcelWorkbook = (
  questions: Question[],
  options: ExportOptions
): XLSX.WorkBook => {
  const workbook = XLSX.utils.book_new();
  const grouped = groupQuestions(questions, options.groupBy);

  Object.entries(grouped).forEach(([sheetName, sheetQuestions]) => {
    const data = sheetQuestions.map((q, i) => formatQuestionForExport(q, i));
    const worksheet = XLSX.utils.json_to_sheet(data);
    
    // Set column widths
    const colWidths = [
      { wch: 5 },   // S.No
      { wch: 60 },  // Question
      { wch: 15 },  // Type
      { wch: 8 },   // Marks
      { wch: 12 },  // Difficulty
      { wch: 15 },  // Bloom Level
      { wch: 50 },  // Options
      { wch: 40 },  // Correct Answer
      { wch: 50 },  // Explanation
      { wch: 25 },  // Topic Tags
      { wch: 12 },  // Vetting Status
      { wch: 30 },  // Vetting Notes
      { wch: 20 },  // Learning Outcome
      { wch: 20 },  // Course Outcomes
    ];
    worksheet['!cols'] = colWidths;
    
    // Sanitize sheet name (Excel has restrictions)
    const sanitizedName = sheetName.substring(0, 31).replace(/[\\/*?[\]]/g, '_');
    XLSX.utils.book_append_sheet(workbook, worksheet, sanitizedName);
  });

  return workbook;
};

/**
 * Generate CSV content
 */
const generateCSV = (questions: Question[]): string => {
  const headers = [
    'S.No', 'Question', 'Type', 'Marks', 'Difficulty', 'Bloom Level',
    'Options', 'Correct Answer', 'Explanation', 'Topic Tags',
    'Vetting Status', 'Vetting Notes', 'Learning Outcome', 'Course Outcomes'
  ];
  
  const escapeCSV = (val: any): string => {
    const str = String(val ?? '');
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const rows = questions.map((q, i) => {
    const formatted = formatQuestionForExport(q, i);
    return headers.map(h => escapeCSV((formatted as any)[h])).join(',');
  });

  return [headers.join(','), ...rows].join('\n');
};

/**
 * Generate DOCX-like content (simplified HTML that can be opened in Word)
 */
const generateDocContent = (
  questions: Question[],
  options: ExportOptions,
  title: string = 'Question Paper'
): string => {
  const grouped = groupQuestions(questions, options.groupBy);
  
  let html = `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>${title}</title>
  <style>
    body { font-family: 'Times New Roman', serif; margin: 40px; }
    h1 { text-align: center; font-size: 24px; margin-bottom: 20px; }
    h2 { font-size: 18px; margin-top: 30px; border-bottom: 1px solid #333; }
    .question { margin: 20px 0; padding: 10px 0; border-bottom: 1px dotted #ccc; }
    .question-text { font-weight: bold; margin-bottom: 10px; }
    .meta { color: #666; font-size: 12px; margin-bottom: 8px; }
    .options { margin-left: 20px; }
    .option { margin: 5px 0; }
    .answer { margin-top: 10px; color: #228B22; }
    .explanation { margin-top: 10px; font-style: italic; color: #444; }
    @media print { .page-break { page-break-before: always; } }
  </style>
</head>
<body>
  <h1>${title}</h1>
`;

  let questionNumber = 1;
  Object.entries(grouped).forEach(([sectionName, sectionQuestions], sectionIndex) => {
    if (options.groupBy !== 'none') {
      html += `<h2>${sectionName}</h2>`;
    }
    
    sectionQuestions.forEach((q) => {
      const typeLabel = q.question_type === 'mcq' ? 'MCQ' : 
                        q.question_type === 'short_answer' ? 'Short Answer' : 'Long Answer';
      
      html += `
  <div class="question">
    <div class="meta">Q${questionNumber}. [${typeLabel}] ${q.marks ? `(${q.marks} marks)` : ''} ${q.difficulty_level ? `- ${q.difficulty_level}` : ''}</div>
    <div class="question-text">${q.question_text}</div>`;
      
      if (q.options && q.options.length > 0) {
        html += `<div class="options">`;
        q.options.forEach((opt, i) => {
          html += `<div class="option">${opt}</div>`;
        });
        html += `</div>`;
      }
      
      if (q.correct_answer) {
        html += `<div class="answer"><strong>Answer:</strong> ${q.correct_answer}</div>`;
      }
      
      if (q.explanation) {
        html += `<div class="explanation"><strong>Explanation:</strong> ${q.explanation}</div>`;
      }
      
      html += `</div>`;
      questionNumber++;
    });
  });

  html += `
</body>
</html>`;

  return html;
};

/**
 * Export questions to file
 */
export const exportQuestions = async (
  questions: Question[],
  options: ExportOptions,
  filename: string = 'questions'
): Promise<ExportResult> => {
  try {
    // Filter by vetting status if specified
    let filteredQuestions = questions;
    if (options.filterVettingStatus && options.filterVettingStatus !== 'all') {
      filteredQuestions = questions.filter(q => q.vetting_status === options.filterVettingStatus);
    }

    if (filteredQuestions.length === 0) {
      return { success: false, error: 'No questions to export' };
    }

    let fileContent: string;
    let fileExtension: string;
    let mimeType: string;

    if (Platform.OS === 'web') {
      // ── Web: use Blob + anchor download (expo-file-system doesn't work on web) ──
      switch (options.format) {
        case 'xlsx': {
          const workbook = generateExcelWorkbook(filteredQuestions, options);
          const wbout = XLSX.write(workbook, { type: 'array', bookType: 'xlsx' });
          webDownload(
            new Uint8Array(wbout),
            `${filename}.xlsx`,
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          );
          return { success: true };
        }
        case 'csv': {
          webDownload(generateCSV(filteredQuestions), `${filename}.csv`, 'text/csv');
          return { success: true };
        }
        case 'docx': {
          webDownload(
            generateDocContent(filteredQuestions, options, filename),
            `${filename}.html`,
            'text/html',
          );
          return { success: true };
        }
        default:
          return { success: false, error: 'Unsupported format' };
      }
    }

    // ── Native (iOS / Android): use expo-file-system + Sharing ──
    switch (options.format) {
      case 'xlsx': {
        const workbook = generateExcelWorkbook(filteredQuestions, options);
        const wbout = XLSX.write(workbook, { type: 'base64', bookType: 'xlsx' });
        const file = new File(Paths.cache, `${filename}.xlsx`);
        const binaryString = atob(wbout);
        const bytes = new Uint8Array(binaryString.length);
        for (let i = 0; i < binaryString.length; i++) {
          bytes[i] = binaryString.charCodeAt(i);
        }
        await file.write(bytes);
        if (await Sharing.isAvailableAsync()) {
          await Sharing.shareAsync(file.uri, {
            mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            dialogTitle: 'Export Questions',
            UTI: 'com.microsoft.excel.xlsx',
          });
        }
        return { success: true, filePath: file.uri };
      }
      case 'csv': {
        fileContent = generateCSV(filteredQuestions);
        fileExtension = 'csv';
        mimeType = 'text/csv';
        break;
      }
      case 'docx': {
        fileContent = generateDocContent(filteredQuestions, options, filename);
        fileExtension = 'html';
        mimeType = 'text/html';
        break;
      }
      default:
        return { success: false, error: 'Unsupported format' };
    }

    const file = new File(Paths.cache, `${filename}.${fileExtension}`);
    await file.write(fileContent);
    if (await Sharing.isAvailableAsync()) {
      await Sharing.shareAsync(file.uri, { mimeType, dialogTitle: 'Export Questions' });
    }
    return { success: true, filePath: file.uri };
  } catch (error) {
    console.error('[Export] Error:', error);
    return { 
      success: false, 
      error: error instanceof Error ? error.message : 'Export failed'
    };
  }
};

/**
 * Export report data
 */
export interface ReportData {
  title: string;
  generatedAt: string;
  summary: {
    totalQuestions: number;
    approvedQuestions: number;
    pendingQuestions: number;
    rejectedQuestions: number;
  };
  byType: Record<string, number>;
  byDifficulty: Record<string, number>;
  byBloomLevel: Record<string, number>;
  byChapter?: Record<string, number>;
  bySubject?: Record<string, number>;
}

export const exportReport = async (
  reportData: ReportData,
  format: ExportFormat,
  filename: string = 'report'
): Promise<ExportResult> => {
  try {
    if (Platform.OS === 'web') {
      if (format === 'xlsx') {
        const workbook = XLSX.utils.book_new();
        const summaryData = [
          ['Report Title', reportData.title],
          ['Generated At', reportData.generatedAt],
          [''], ['Summary'],
          ['Total Questions', reportData.summary.totalQuestions],
          ['Approved', reportData.summary.approvedQuestions],
          ['Pending', reportData.summary.pendingQuestions],
          ['Rejected', reportData.summary.rejectedQuestions],
        ];
        XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet(summaryData), 'Summary');
        XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([['Question Type', 'Count'], ...Object.entries(reportData.byType)]), 'By Type');
        XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([['Difficulty', 'Count'], ...Object.entries(reportData.byDifficulty)]), 'By Difficulty');
        XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([['Bloom Level', 'Count'], ...Object.entries(reportData.byBloomLevel)]), 'By Bloom Level');
        if (reportData.byChapter && Object.keys(reportData.byChapter).length > 0)
          XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([['Chapter', 'Count'], ...Object.entries(reportData.byChapter)]), 'By Chapter');
        if (reportData.bySubject && Object.keys(reportData.bySubject).length > 0)
          XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([['Subject', 'Count'], ...Object.entries(reportData.bySubject)]), 'By Subject');
        const wbout = XLSX.write(workbook, { type: 'array', bookType: 'xlsx' });
        webDownload(new Uint8Array(wbout), `${filename}.xlsx`, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
        return { success: true };
      }
      if (format === 'csv') {
        const lines = [
          `Report: ${reportData.title}`, `Generated: ${reportData.generatedAt}`, '',
          'Summary',
          `Total Questions,${reportData.summary.totalQuestions}`,
          `Approved,${reportData.summary.approvedQuestions}`,
          `Pending,${reportData.summary.pendingQuestions}`,
          `Rejected,${reportData.summary.rejectedQuestions}`,
          '', 'By Type', ...Object.entries(reportData.byType).map(([k, v]) => `${k},${v}`),
          '', 'By Difficulty', ...Object.entries(reportData.byDifficulty).map(([k, v]) => `${k},${v}`),
          '', 'By Bloom Level', ...Object.entries(reportData.byBloomLevel).map(([k, v]) => `${k},${v}`),
        ];
        webDownload(lines.join('\n'), `${filename}.csv`, 'text/csv');
        return { success: true };
      }
      return { success: false, error: 'Unsupported format for reports' };
    }

    // ── Native ──
    if (format === 'xlsx') {
      const workbook = XLSX.utils.book_new();
      const summaryData = [
        ['Report Title', reportData.title], ['Generated At', reportData.generatedAt],
        [''], ['Summary'],
        ['Total Questions', reportData.summary.totalQuestions],
        ['Approved', reportData.summary.approvedQuestions],
        ['Pending', reportData.summary.pendingQuestions],
        ['Rejected', reportData.summary.rejectedQuestions],
      ];
      XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet(summaryData), 'Summary');
      XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([['Question Type', 'Count'], ...Object.entries(reportData.byType)]), 'By Type');
      XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([['Difficulty', 'Count'], ...Object.entries(reportData.byDifficulty)]), 'By Difficulty');
      XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([['Bloom Level', 'Count'], ...Object.entries(reportData.byBloomLevel)]), 'By Bloom Level');
      const wbout = XLSX.write(workbook, { type: 'base64', bookType: 'xlsx' });
      const file = new File(Paths.cache, `${filename}.xlsx`);
      const binaryString = atob(wbout);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) bytes[i] = binaryString.charCodeAt(i);
      await file.write(bytes);
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(file.uri, { mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', dialogTitle: 'Export Report' });
      }
      return { success: true, filePath: file.uri };
    }
    if (format === 'csv') {
      const lines = [
        `Report: ${reportData.title}`, `Generated: ${reportData.generatedAt}`, '',
        'Summary',
        `Total Questions,${reportData.summary.totalQuestions}`,
        `Approved,${reportData.summary.approvedQuestions}`,
        `Pending,${reportData.summary.pendingQuestions}`,
        `Rejected,${reportData.summary.rejectedQuestions}`,
        '', 'By Type', ...Object.entries(reportData.byType).map(([k, v]) => `${k},${v}`),
      ];
      const file = new File(Paths.cache, `${filename}.csv`);
      await file.write(lines.join('\n'));
      if (await Sharing.isAvailableAsync()) await Sharing.shareAsync(file.uri, { mimeType: 'text/csv' });
      return { success: true, filePath: file.uri };
    }
    return { success: false, error: 'Unsupported format for reports' };
  } catch (error) {
    console.error('[ExportReport] Error:', error);
    return { success: false, error: error instanceof Error ? error.message : 'Export failed' };
  }
};

export default {
  exportQuestions,
  exportReport,
};
