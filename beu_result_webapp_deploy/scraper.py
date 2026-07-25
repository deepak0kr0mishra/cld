import json
import os
import time
from typing import Callable, Optional

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# Roll range used by BEU branch batches.
START_ROLL = 1
END_ROLL = 135
MAX_CONSECUTIVE_NOT_FOUND = 4

# Result configuration for the current B.Tech 1st Semester result page.
BASE_URL = "https://beu-bih.ac.in/result-two/B.Tech%201st%20Semester%20Examination%202025?d=eyJzZW1lc3RlciI6MSwic2Vzc2lvbiI6IjIwMjUiLCJleGFtX2hlbGQiOiJKYW51YXJ5LzIwMjYiLCJleGFtX2lkIjoiMjUwMTAxTiJ9"
SEMESTER = "I"
EXAM_HELD = "January/2026"
EXAM_ID = "250101N"
DEFAULT_YEAR = "2025"
DEFAULT_BRANCH_CODE = "105"
DEFAULT_COLLEGE_CODE = "157"


ProgressCallback = Callable[[dict], None]


def normalize_year(year: str) -> tuple[str, str]:
    clean = "".join(ch for ch in str(year).strip() if ch.isdigit())
    if len(clean) == 2:
        return f"20{clean}", clean
    if len(clean) == 4:
        return clean, clean[-2:]
    raise ValueError("Year must be 2 digits like 25 or 4 digits like 2025.")


def normalize_code(value: str, width: int, label: str) -> str:
    clean = "".join(ch for ch in str(value).strip() if ch.isdigit())
    if not clean:
        raise ValueError(f"{label} is required.")
    if len(clean) > width:
        raise ValueError(f"{label} must be at most {width} digits.")
    return clean.zfill(width)


def build_registration_prefix(year: str, branch_code: str, college_code: str) -> tuple[str, str]:
    api_year, reg_year = normalize_year(year)
    branch = normalize_code(branch_code, 3, "Branch code")
    college = normalize_code(college_code, 3, "College code")
    return f"{reg_year}{branch}{college}", api_year


def emit(progress_callback: Optional[ProgressCallback], event: dict) -> None:
    if progress_callback:
        progress_callback(event)


def scrape_results(
    college_code: str = DEFAULT_COLLEGE_CODE,
    year: str = DEFAULT_YEAR,
    branch_code: str = DEFAULT_BRANCH_CODE,
    start_roll: int = START_ROLL,
    end_roll: int = END_ROLL,
    max_consecutive_not_found: int = MAX_CONSECUTIVE_NOT_FOUND,
    output_filename: Optional[str] = "beu_bulk_automation_results.json",
    progress_callback: Optional[ProgressCallback] = None,
) -> list[dict]:
    reg_prefix, api_year = build_registration_prefix(year, branch_code, college_code)
    total_rolls = end_roll - start_roll + 1

    emit(
        progress_callback,
        {
            "type": "started",
            "message": "Starting browser",
            "prefix": reg_prefix,
            "apiYear": api_year,
            "totalRolls": total_rolls,
        },
    )

    print("Starting Undetected Chromedriver (Version 149)...")

    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    if os.environ.get("HEADLESS", "1") == "1":
        options.add_argument("--headless=new")

    version_main = os.environ.get("CHROME_VERSION_MAIN")
    driver_kwargs = {"options": options}
    if version_main:
        driver_kwargs["version_main"] = int(version_main)

    driver = uc.Chrome(**driver_kwargs)
    final_results: list[dict] = []
    consecutive_not_found = 0

    try:
        for index, roll_no in enumerate(range(start_roll, end_roll + 1), start=1):
            reg_no = f"{reg_prefix}{roll_no:03d}"
            print(f"\n[+] Processing Registration Number: {reg_no}")
            emit(
                progress_callback,
                {
                    "type": "processing",
                    "message": f"Processing {reg_no}",
                    "regNo": reg_no,
                    "current": index,
                    "total": total_rolls,
                    "consecutiveFailures": consecutive_not_found,
                },
            )

            driver.get(BASE_URL)

            wait = WebDriverWait(driver, 20)
            reg_input = wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Enter Reg. No.']"))
            )

            reg_input.clear()
            reg_input.send_keys(reg_no)
            print(f"-> Filled registration number: {reg_no}")

            print("-> Waiting for Cloudflare Turnstile to verify 'Success!'...")
            captcha_token = None

            for _ in range(60):
                try:
                    token_val = driver.execute_script(
                        'return document.querySelector("[name=\'cf-turnstile-response\']").value;'
                    )
                    if token_val and len(token_val) > 10:
                        captcha_token = token_val
                        print("-> Cloudflare Captcha Automatically Verified (Success!)")
                        break
                except Exception:
                    pass
                time.sleep(1)

            if not captcha_token:
                result = {"regNo": reg_no, "status": "Failed", "message": "Captcha Timeout"}
                final_results.append(result)
                emit(progress_callback, {"type": "record", "record": result, "resultCount": len(final_results)})
                continue

            try:
                print("-> Passing live captcha token to session generator...")

                token_fetch_url = f"https://beu-bih.ac.in/backend/v1/result/token?captcha={captcha_token}"
                token_js_script = f"""
                    return fetch('{token_fetch_url}')
                        .then(res => res.json())
                        .then(data => data.token);
                """
                session_token = driver.execute_script(token_js_script)

                if not session_token:
                    result = {"regNo": reg_no, "status": "Failed", "message": "Token Authorization Refused"}
                    final_results.append(result)
                    emit(progress_callback, {"type": "record", "record": result, "resultCount": len(final_results)})
                    continue

                print("-> Authorization success! Extracting result payload...")

                result_api_url = (
                    "https://beu-bih.ac.in/backend/v1/result/get-result"
                    f"?year={api_year}&redg_no={reg_no}&semester={SEMESTER}"
                    f"&exam_held={EXAM_HELD}&exam_id={EXAM_ID}&token={session_token}"
                )

                result_js_script = f"""
                    return fetch('{result_api_url}')
                        .then(res => res.json());
                """
                api_response = driver.execute_script(result_js_script)

                if api_response and api_response.get("status") == 200:
                    student_data = api_response.get("data")
                    final_results.append(student_data)
                    consecutive_not_found = 0
                    print(f"[+] Success: Data extracted for {student_data.get('name', reg_no)}")
                    emit(
                        progress_callback,
                        {
                            "type": "record",
                            "record": student_data,
                            "resultCount": len(final_results),
                            "consecutiveFailures": consecutive_not_found,
                        },
                    )
                else:
                    message = api_response.get("message", "Unknown Error") if api_response else "No API response"
                    consecutive_not_found += 1
                    result = {"regNo": reg_no, "status": "Failed", "message": message}
                    final_results.append(result)
                    print(f"[-] Failed for {reg_no}: {message}")
                    print(f"-> Consecutive result failures: {consecutive_not_found}/{max_consecutive_not_found}")
                    emit(
                        progress_callback,
                        {
                            "type": "record",
                            "record": result,
                            "resultCount": len(final_results),
                            "consecutiveFailures": consecutive_not_found,
                        },
                    )
                    if consecutive_not_found >= max_consecutive_not_found:
                        print(f"[!] Stopping early after {max_consecutive_not_found} consecutive result failures.")
                        emit(
                            progress_callback,
                            {
                                "type": "stopping",
                                "message": f"Stopped after {max_consecutive_not_found} consecutive failures",
                                "consecutiveFailures": consecutive_not_found,
                            },
                        )
                        break

            except Exception as exc:
                result = {"regNo": reg_no, "status": "Error", "message": str(exc)}
                print(f"[-] Script execution engine broken: {exc}")
                final_results.append(result)
                emit(progress_callback, {"type": "record", "record": result, "resultCount": len(final_results)})

            time.sleep(2)

    finally:
        if output_filename:
            with open(output_filename, "w", encoding="utf-8") as file:
                json.dump(final_results, file, indent=4, ensure_ascii=False)

            print(f"\n[!!!] Scraper processing complete. Saved to '{output_filename}'.")

        emit(
            progress_callback,
            {
                "type": "finished",
                "message": "Scrape finished",
                "resultCount": len(final_results),
                "results": final_results,
            },
        )
        driver.quit()

    return final_results


def run_scraper() -> None:
    scrape_results()


if __name__ == "__main__":
    run_scraper()
