import { createClient } from '@supabase/supabase-js';

// Supabase 클라이언트 초기화
const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_KEY
);

/**
 * 현재 한국 시간을 반환
 */
function getKSTNow() {
  const now = new Date();
  const kstOffset = 9 * 60; // KST는 UTC+9
  const utc = now.getTime() + (now.getTimezoneOffset() * 60000);
  return new Date(utc + (kstOffset * 60000));
}

/**
 * 날짜를 YYYY-MM-DD 형식으로 변환
 */
function formatDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * 오늘부터 한 달 이내의 온콜 스케줄 조회
 */
async function getOncallSchedule() {
  const today = getKSTNow();
  const endDate = new Date(today);
  endDate.setDate(endDate.getDate() + 30);

  try {
    const { data, error } = await supabase
      .from('oncall_rotation')
      .select('*')
      .gte('date', formatDate(today))
      .lte('date', formatDate(endDate))
      .order('date');

    if (error) {
      console.error('Supabase error:', error);
      return [];
    }

    return data || [];
  } catch (error) {
    console.error('Error getting schedule from Supabase:', error);
    return [];
  }
}

/**
 * Slack 메시지 포맷으로 변환
 */
function formatSlackMessage(scheduleData) {
  if (!scheduleData || scheduleData.length === 0) {
    return {
      response_type: 'in_channel',
      text: '📅 향후 30일간 예정된 온콜 스케줄이 없습니다.'
    };
  }

  // Block Kit 형식으로 메시지 구성
  const blocks = [
    {
      type: 'header',
      text: {
        type: 'plain_text',
        text: '📅 온콜 스케줄 (향후 30일)',
        emoji: true
      }
    },
    {
      type: 'divider'
    }
  ];

  // 요일 한글 매핑
  const weekdayMap = {
    'Sun': '일',
    'Mon': '월',
    'Tue': '화',
    'Wed': '수',
    'Thu': '목',
    'Fri': '금',
    'Sat': '토'
  };

  // 월별로 그룹화하여 표시
  let currentMonth = null;

  scheduleData.forEach(item => {
    const dateObj = new Date(item.date + 'T00:00:00+09:00'); // KST 기준
    const year = dateObj.getFullYear();
    const month = dateObj.getMonth() + 1;
    const day = dateObj.getDate();
    const weekday = dateObj.toLocaleDateString('en-US', { weekday: 'short' });

    const monthStr = `${year}년 ${String(month).padStart(2, '0')}월`;
    const dayStr = `${String(month).padStart(2, '0')}월 ${String(day).padStart(2, '0')}일 (${weekdayMap[weekday]})`;

    // 월이 바뀌면 월 헤더 추가
    if (currentMonth !== monthStr) {
      currentMonth = monthStr;
      blocks.push({
        type: 'section',
        text: {
          type: 'mrkdwn',
          text: `*${monthStr}*`
        }
      });
    }

    // 날짜와 담당자 표시
    blocks.push({
      type: 'section',
      text: {
        type: 'mrkdwn',
        text: `• \`${dayStr}\` - ${item.member}`
      }
    });
  });

  // 푸터 추가
  const now = getKSTNow();
  const timestamp = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')} KST`;

  blocks.push(
    {
      type: 'divider'
    },
    {
      type: 'context',
      elements: [
        {
          type: 'mrkdwn',
          text: `_마지막 업데이트: ${timestamp}_`
        }
      ]
    }
  );

  return {
    response_type: 'in_channel',
    blocks: blocks
  };
}

/**
 * Vercel Serverless Function 핸들러
 */
export default async function handler(req, res) {
  // POST 요청만 허용 (Slack slash command는 POST로 전송됨)
  if (req.method !== 'POST') {
    // GET 요청은 테스트용으로 간단한 메시지 반환
    return res.status(200).json({
      message: 'Oncall Schedule Webhook is running!',
      usage: "This endpoint is designed for Slack slash command '/온콜리스트'"
    });
  }

  try {
    // 선택사항: Slack verification token 검증
    // const { token } = req.body;
    // if (token !== process.env.SLACK_VERIFICATION_TOKEN) {
    //   return res.status(403).json({ error: 'Invalid token' });
    // }

    // 온콜 스케줄 조회
    const schedule = await getOncallSchedule();

    // Slack 메시지 포맷으로 변환
    const slackResponse = formatSlackMessage(schedule);

    // 응답 전송
    return res.status(200).json(slackResponse);

  } catch (error) {
    console.error('Error in handler:', error);

    // 에러 응답
    return res.status(500).json({
      response_type: 'ephemeral',
      text: `⚠️ 오류가 발생했습니다: ${error.message}`
    });
  }
}
